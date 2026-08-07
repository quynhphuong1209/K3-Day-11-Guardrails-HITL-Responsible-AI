"""Flask server for the stateful VinBank chatbot demo."""
from __future__ import annotations

import asyncio
import concurrent.futures
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agents.agent import create_protected_agent
from core.utils import chat_with_agent
from guardrails.input_guardrails import (
    GuardrailState,
    InputGuardrailPlugin,
    contains_blocked_topic,
    detect_injection,
)
from guardrails.output_guardrails import OutputGuardrailPlugin

MAX_CONVERSATIONS = 20
CONVERSATION_TTL_SECONDS = 30 * 60
MAX_MESSAGE_LENGTH = 4_000
MODEL_TIMEOUT_SECONDS = 120


class AsyncBridge:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=MODEL_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError("Model request timed out")


@dataclass
class ConversationBundle:
    agent: Any
    runner: Any
    input_plugin: InputGuardrailPlugin
    output_plugin: OutputGuardrailPlugin
    session_id: str | None = None
    last_accessed: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)


app = Flask(__name__)
CORS(app)

_async_bridge = AsyncBridge()
_registry: dict[str, ConversationBundle] = {}
_registry_lock = threading.Lock()


def _parse_conversation_id(value) -> str:
    if value in (None, ""):
        return str(uuid.uuid4())
    if not isinstance(value, str):
        raise ValueError("invalid_conversation_id")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ValueError("invalid_conversation_id") from exc


def _create_bundle() -> ConversationBundle:
    state = GuardrailState()
    input_plugin = InputGuardrailPlugin(state, allow_off_topic=True)
    output_plugin = OutputGuardrailPlugin(state, use_llm_judge=False)
    agent, runner = create_protected_agent(plugins=[input_plugin, output_plugin])
    return ConversationBundle(
        agent=agent,
        runner=runner,
        input_plugin=input_plugin,
        output_plugin=output_plugin,
    )


def _remove_expired_conversations(now: float):
    expired_ids = [
        conversation_id
        for conversation_id, bundle in _registry.items()
        if not bundle.lock.locked()
        and now - bundle.last_accessed > CONVERSATION_TTL_SECONDS
    ]
    for conversation_id in expired_ids:
        _registry.pop(conversation_id, None)


def _get_or_create_bundle(conversation_id: str) -> tuple[ConversationBundle, bool]:
    now = time.monotonic()
    with _registry_lock:
        _remove_expired_conversations(now)
        bundle = _registry.get(conversation_id)
        if bundle is not None:
            bundle.last_accessed = now
            return bundle, False

        if len(_registry) >= MAX_CONVERSATIONS:
            available = [
                (candidate_id, candidate)
                for candidate_id, candidate in _registry.items()
                if not candidate.lock.locked()
            ]
            if not available:
                raise RuntimeError("registry_busy")
            oldest_id, _ = min(available, key=lambda item: item[1].last_accessed)
            _registry.pop(oldest_id, None)

        bundle = _create_bundle()
        _registry[conversation_id] = bundle
        return bundle, True


def _error_response(message: str, code: str, status: int, conversation_id=None):
    payload = {
        "response": message,
        "blocked": False,
        "error": code,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    return jsonify(payload), status


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(Path(__file__).resolve().parent, "chat.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error_response("Dữ liệu gửi lên không hợp lệ.", "invalid_json", 400)

    try:
        conversation_id = _parse_conversation_id(data.get("conversation_id"))
    except ValueError:
        return _error_response(
            "Mã cuộc trò chuyện không hợp lệ.", "invalid_conversation_id", 400
        )

    user_message = data.get("message")
    if not isinstance(user_message, str) or not user_message.strip():
        return _error_response(
            "Vui lòng nhập nội dung tin nhắn.",
            "invalid_message",
            400,
            conversation_id,
        )
    user_message = user_message.strip()
    if len(user_message) > MAX_MESSAGE_LENGTH:
        return _error_response(
            "Tin nhắn quá dài. Vui lòng rút gọn nội dung.",
            "message_too_long",
            413,
            conversation_id,
        )

    if detect_injection(user_message):
        return jsonify({
            "conversation_id": conversation_id,
            "response": (
                "Yêu cầu bị chặn: phát hiện prompt injection. "
                "Tôi chỉ xử lý các yêu cầu an toàn."
            ),
            "blocked": True,
            "block_reason": "prompt_injection",
            "context_status": "not_used",
        })

    if contains_blocked_topic(user_message):
        return jsonify({
            "conversation_id": conversation_id,
            "response": "Yêu cầu bị chặn vì chứa nội dung nguy hiểm.",
            "blocked": True,
            "block_reason": "unsafe_topic",
            "context_status": "not_used",
        })

    try:
        bundle, bundle_created = _get_or_create_bundle(conversation_id)
    except RuntimeError:
        return _error_response(
            "Máy chủ đang xử lý quá nhiều cuộc trò chuyện. Vui lòng thử lại.",
            "registry_busy",
            503,
            conversation_id,
        )

    try:
        with bundle.lock:
            previous_session_id = bundle.session_id
            input_blocked_before = bundle.input_plugin.blocked_count
            output_blocked_before = bundle.output_plugin.blocked_count

            response_text, session = _async_bridge.run(
                chat_with_agent(
                    bundle.agent,
                    bundle.runner,
                    user_message,
                    session_id=previous_session_id,
                )
            )
            bundle.session_id = session.id
            bundle.last_accessed = time.monotonic()

            is_blocked = (
                bundle.input_plugin.blocked_count > input_blocked_before
                or bundle.output_plugin.blocked_count > output_blocked_before
            )
            if bundle_created or previous_session_id is None:
                context_status = "created"
            elif previous_session_id != session.id:
                context_status = "reset"
            else:
                context_status = "continued"

        return jsonify({
            "conversation_id": conversation_id,
            "response": response_text,
            "blocked": is_blocked,
            "context_status": context_status,
        })
    except Exception as exc:
        app.logger.error("Chat request failed: %s", type(exc).__name__)
        error_text = str(exc)
        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            message = "Gemini API đã hết quota. Vui lòng kiểm tra API key hoặc thử lại sau."
            code = "quota_exhausted"
        elif isinstance(exc, TimeoutError):
            message = "Phản hồi đang mất quá nhiều thời gian. Vui lòng thử lại."
            code = "model_timeout"
        else:
            message = "Xin lỗi, dịch vụ hiện không thể xử lý yêu cầu. Vui lòng thử lại."
            code = "model_unavailable"
        return _error_response(message, code, 503, conversation_id)


@app.route("/conversations/<conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id):
    try:
        normalized_id = _parse_conversation_id(conversation_id)
    except ValueError:
        return _error_response(
            "Mã cuộc trò chuyện không hợp lệ.", "invalid_conversation_id", 400
        )

    with _registry_lock:
        bundle = _registry.get(normalized_id)
        if bundle is None:
            return "", 204
        if not bundle.lock.acquire(blocking=False):
            return _error_response(
                "Cuộc trò chuyện đang xử lý tin nhắn.",
                "conversation_busy",
                409,
                normalized_id,
            )
        try:
            _registry.pop(normalized_id, None)
        finally:
            bundle.lock.release()
    return "", 204


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "guardrails": "active"})


if __name__ == "__main__":
    print("VinBank Chatbot Server: http://localhost:8000")
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)
