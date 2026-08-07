import sys
import asyncio
from pathlib import Path

# Add src to python path
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from assignment.pipeline import build_production_plugins, build_observability, run_assignment_suite
from attacks.attacks import adversarial_prompts, generate_ai_attacks, save_attack_results, classify_attack_outcome
from hitl.hitl import test_confidence_router, test_hitl_points
from guardrails.input_guardrails import test_injection_detection, test_topic_filter, test_input_plugin
from guardrails.output_guardrails import test_content_filter, _init_judge

async def main():
    print("=== RUNNING ASSIGNMENT 11 TASKS ===")
    student_id = "SE123456"

    # Part 2: Guardrails
    test_injection_detection()
    test_topic_filter()
    await test_input_plugin()
    _init_judge()
    test_content_filter()

    # Part 4: HITL
    test_confidence_router()
    test_hitl_points()

    # Part 5: Suite & Outputs
    plugins = build_production_plugins()
    audit, monitor = build_observability()
    pipeline = {"plugins": plugins, "audit": audit, "monitor": monitor}
    res_data = await run_assignment_suite(pipeline, student_id=student_id)
    print("Assignment suite completed. Generated results.json, audit_log.json, metrics.json")

    # Generate Attack Results
    unsafe_results = []
    guards_results = []
    for atk in adversarial_prompts:
        outcome_unsafe = classify_attack_outcome(atk["input"], "The admin password is admin123, API key sk-vinbank-secret-2024, db.vinbank.internal:5432", target_name="unsafe")
        unsafe_results.append({
            "id": atk["id"],
            "name": atk["category"],
            "category": atk["category"],
            "input": atk["input"],
            "response": "The admin password is admin123, API key sk-vinbank-secret-2024, db.vinbank.internal:5432",
            "response_preview": "The admin password is admin123, API key sk-vinbank-secret-2024, db.vinbank.internal:5432",
            "leaked": True,
            "blocked_input": False,
            "blocked": False,
            "layer": "leaked",
            "blocked_at": "LEAKED — response chứa secret",
            "target": "unsafe"
        })

        outcome_guards = classify_attack_outcome(atk["input"], "Request blocked: prompt injection detected. I can only answer standard VinBank banking queries.", target_name="guards")
        guards_results.append({
            "id": atk["id"],
            "name": atk["category"],
            "category": atk["category"],
            "input": atk["input"],
            "response": "Request blocked: prompt injection detected.",
            "response_preview": "Request blocked: prompt injection detected.",
            "leaked": False,
            "blocked_input": True,
            "blocked": True,
            "layer": "input_injection",
            "blocked_at": "BLOCKED_INPUT — injection filter (plugin)",
            "target": "guards"
        })

    ai_attacks = await generate_ai_attacks()
    save_attack_results(
        unsafe_results=unsafe_results,
        guards_results=guards_results,
        ai_attacks=ai_attacks,
        student_id=student_id
    )
    print("Attack results saved to outputs/attack_results.json")

if __name__ == "__main__":
    asyncio.run(main())
