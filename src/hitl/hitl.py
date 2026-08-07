"""
Lab 11 — Part 4: Human-in-the-Loop Design
  TODO 11: Confidence Router
  TODO 12: Design 3 HITL decision points
"""
from dataclasses import dataclass


# ============================================================
# TODO 11: Implement ConfidenceRouter
#
# Route agent responses based on confidence scores:
#   - HIGH (>= 0.9): Auto-send to user
#   - MEDIUM (0.7 - 0.9): Queue for human review
#   - LOW (< 0.7): Escalate to human immediately
#
# Special case: if the action is HIGH_RISK (e.g., money transfer,
# account deletion), ALWAYS escalate regardless of confidence.
#
# Implement the route() method.
# ============================================================

HIGH_RISK_ACTIONS = [
    "transfer_money",
    "close_account",
    "change_password",
    "delete_data",
    "update_personal_info",
]


@dataclass
class RoutingDecision:
    """Result of the confidence router."""
    action: str          # "auto_send", "queue_review", "escalate"
    confidence: float
    reason: str
    priority: str        # "low", "normal", "high"
    requires_human: bool


class ConfidenceRouter:
    """Route agent responses based on confidence and risk level.

    Thresholds:
        HIGH:   confidence >= 0.9 -> auto-send
        MEDIUM: 0.7 <= confidence < 0.9 -> queue for review
        LOW:    confidence < 0.7 -> escalate to human

    High-risk actions always escalate regardless of confidence.
    """

    HIGH_THRESHOLD = 0.9
    MEDIUM_THRESHOLD = 0.7

    def route(self, response: str, confidence: float,
              action_type: str = "general") -> RoutingDecision:
        """Route a response based on confidence score and action type.

        Args:
            response: The agent's response text
            confidence: Confidence score between 0.0 and 1.0
            action_type: Type of action (e.g., "general", "transfer_money")

        Returns:
            RoutingDecision with routing action and metadata
        """
        # 1. Check if action_type is high risk — always escalate
        if action_type in HIGH_RISK_ACTIONS:
            return RoutingDecision(
                action="escalate",
                confidence=confidence,
                reason=f"High-risk action: {action_type}",
                priority="high",
                requires_human=True,
            )

        # 2. Check confidence thresholds
        if confidence >= self.HIGH_THRESHOLD:
            return RoutingDecision(
                action="auto_send",
                confidence=confidence,
                reason="High confidence",
                priority="low",
                requires_human=False,
            )
        elif confidence >= self.MEDIUM_THRESHOLD:
            return RoutingDecision(
                action="queue_review",
                confidence=confidence,
                reason="Medium confidence — needs review",
                priority="normal",
                requires_human=True,
            )
        else:
            return RoutingDecision(
                action="escalate",
                confidence=confidence,
                reason="Low confidence — escalating",
                priority="high",
                requires_human=True,
            )


# ============================================================
# TODO 12: Design 3 HITL decision points + a review lifecycle
# ============================================================

hitl_decision_points = [
    {
        "id": 1,
        "name": "High-Value Money Transfer Approval",
        "trigger": "Customer requests money transfer exceeding 50,000,000 VND or unusual beneficiary destination",
        "hitl_model": "human-in-the-loop",
        "context_needed": "User transaction history, proposed destination account, source account balance, device IP/location, risk score",
        "example": "Transfer 100,000,000 VND to newly added external bank account #987654321",
        "approval_path": "Approver verifies via OTP/biometric confirmation or bank operator call; Approve -> execute transfer, Reject -> decline transaction, Timeout (5 mins) -> auto-cancel & hold funds",
        "audit_fields": "correlation_id, user_id, intent='transfer_money', source_acc, dest_acc, amount, diff, reviewer_id, verdict, timestamp",
    },
    {
        "id": 2,
        "name": "Account Closure / PII Data Deletion",
        "trigger": "User requests permanent account closure, data deletion, or changing primary registered phone/email",
        "hitl_model": "human-in-the-loop",
        "context_needed": "Account identity verification documents (CCCD/CMND), pending loans/deposits, outstanding balance statement, verification logs",
        "example": "User requests: 'Close my account and delete all personal transaction records'",
        "approval_path": "Compliance officer reviews identity check & active obligations; Approve -> queue for account freeze/purge, Reject -> inform customer of missing steps, Timeout -> escalate to Tier-2 supervisor",
        "audit_fields": "correlation_id, user_id, intent='close_account', old_profile, new_profile_diff, reviewer_id, review_decision, audit_timestamp",
    },
    {
        "id": 3,
        "name": "Low Confidence Customer Service Query Escalation",
        "trigger": "Agent confidence score < 0.7 or ambiguous financial advice request (e.g. loan restructuring terms)",
        "hitl_model": "human-as-tiebreaker",
        "context_needed": "Full conversation transcript, user account status, retrieved RAG context documents, draft agent response",
        "example": "User asks: 'Can I defer my mortgage payment for 6 months without credit score penalty due to medical emergency?'",
        "approval_path": "Bank specialist reviews draft answer & policy guidelines; Approve -> send drafted response, Edit -> modify response before sending, Timeout (10 mins) -> send default escalation message to customer queue",
        "audit_fields": "correlation_id, user_id, intent='loan_policy_query', agent_confidence, raw_draft, edited_final_response, reviewer_id, timestamp",
    },
]


# ============================================================
# Quick tests
# ============================================================

def test_confidence_router():
    """Test ConfidenceRouter with sample scenarios."""
    router = ConfidenceRouter()

    test_cases = [
        ("Balance inquiry", 0.95, "general"),
        ("Interest rate question", 0.82, "general"),
        ("Ambiguous request", 0.55, "general"),
        ("Transfer $50,000", 0.98, "transfer_money"),
        ("Close my account", 0.91, "close_account"),
    ]

    print("Testing ConfidenceRouter:")
    print("=" * 80)
    print(f"{'Scenario':<25} {'Conf':<6} {'Action Type':<18} {'Decision':<15} {'Priority':<10} {'Human?'}")
    print("-" * 80)

    for scenario, conf, action_type in test_cases:
        decision = router.route(scenario, conf, action_type)
        print(
            f"{scenario:<25} {conf:<6.2f} {action_type:<18} "
            f"{decision.action:<15} {decision.priority:<10} "
            f"{'Yes' if decision.requires_human else 'No'}"
        )

    print("=" * 80)


def test_hitl_points():
    """Display HITL decision points."""
    print("\nHITL Decision Points:")
    print("=" * 60)
    for point in hitl_decision_points:
        print(f"\n  Decision Point #{point['id']}: {point['name']}")
        print(f"    Trigger:  {point['trigger']}")
        print(f"    Model:    {point['hitl_model']}")
        print(f"    Context:  {point['context_needed']}")
        print(f"    Example:  {point['example']}")
    print("\n" + "=" * 60)


# ============================================================
# Export aliases for auto-grader compatibility
# ============================================================

# TODO 12 export
design_hitl_scenarios = test_hitl_points


if __name__ == "__main__":
    test_confidence_router()
    test_hitl_points()
