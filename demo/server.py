"""
Simple Flask server for chatbot demo
Connects to the protected agent with guardrails
"""
import sys
import asyncio
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agents.agent import create_protected_agent
from guardrails.input_guardrails import InputGuardrailPlugin
from guardrails.output_guardrails import OutputGuardrailPlugin
from core.utils import chat_with_agent

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Initialize protected agent
input_plugin = InputGuardrailPlugin()
output_plugin = OutputGuardrailPlugin(use_llm_judge=False)
agent, runner = create_protected_agent(plugins=[input_plugin, output_plugin])

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages from frontend."""
    data = request.get_json()
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        # Run async chat
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response, metadata = loop.run_until_complete(
            chat_with_agent(agent, runner, user_message)
        )
        loop.close()

        # Check if blocked
        is_blocked = "blocked:" in response.lower() or "[redacted]" in response.lower()

        return jsonify({
            'response': response,
            'blocked': is_blocked,
            'metadata': metadata
        })

    except Exception as e:
        return jsonify({
            'response': f"Xin lỗi, đã xảy ra lỗi: {str(e)}",
            'blocked': True,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'guardrails': 'active'})

if __name__ == '__main__':
    print("=" * 60)
    print("VinBank Chatbot Server")
    print("=" * 60)
    print("Server: http://localhost:8000")
    print("Frontend: Open demo/chat.html in browser")
    print("Guardrails: Input + Output filters active")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8000, debug=True)
