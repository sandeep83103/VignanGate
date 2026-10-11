from sqlalchemy.ext.asyncio import AsyncSession
from backend.ai_engine.base_agent import BaseAgent
from backend.ai_engine.context import AccessContext

class PolicyAgent(BaseAgent):
    """
    AGENT 5: Policy Agent
    Acts as the final access arbitrator.
    Synthesizes identity, authorization, risk, and anomaly inputs into actionable routing:
    - FAST_LANE_GRANT: Low risk, clean anomaly, verified credentials -> OPEN_BARRIER.
    - STANDARD_INSPECT: Medium risk or visitor pass -> HOLD_CLOSED for guard verification.
    - MANUAL_REVIEW_DENY: High risk, fraud detected, or suspended user -> LOCK_BARRIER.
    """

    def __init__(self):
        super().__init__("Policy Agent")

    async def evaluate(self, ctx: AccessContext, db: AsyncSession) -> AccessContext:
        # Check hard failure conditions
        if ctx.identity_status in ["SUSPENDED", "MALFORMED"]:
            ctx.policy_decision = "MANUAL_REVIEW_DENY"
            ctx.barrier_command = "LOCK_BARRIER"
            ctx.final_reason = f"Account {ctx.identity_status}: Access rejected by campus security policy."
            return ctx

        if ctx.has_anomaly:
            ctx.policy_decision = "MANUAL_REVIEW_DENY"
            ctx.barrier_command = "LOCK_BARRIER"
            ctx.final_reason = f"Security Policy Violation: {ctx.anomaly_flags[0]}"
            return ctx

        if ctx.auth_status in ["CURFEW_RESTRICTED", "UNAUTHORIZED"]:
            ctx.policy_decision = "MANUAL_REVIEW_DENY"
            ctx.barrier_command = "LOCK_BARRIER"
            ctx.final_reason = f"Authorization Denied: {ctx.auth_reason}"
            return ctx

        if ctx.identity_status == "UNREGISTERED":
            ctx.policy_decision = "MANUAL_REVIEW_DENY"
            ctx.barrier_command = "LOCK_BARRIER"
            ctx.final_reason = "Unregistered credential UID: Guard inspection required."
            return ctx

        # Check clean Fast Lane condition
        if (
            ctx.identity_status == "VERIFIED" and
            ctx.auth_status == "AUTHORIZED" and
            ctx.risk_level == "LOW" and
            not ctx.has_anomaly
        ):
            ctx.policy_decision = "FAST_LANE_GRANT"
            ctx.barrier_command = "OPEN_BARRIER"
            ctx.final_reason = f"Fast-lane entry clearance granted for {ctx.full_name} ({ctx.role})."
            return ctx

        # Medium risk routing
        if ctx.risk_level == "MEDIUM":
            ctx.policy_decision = "STANDARD_INSPECT"
            ctx.barrier_command = "HOLD_CLOSED"
            ctx.final_reason = f"Medium risk factor detected ({ctx.risk_score}/100): Guard review advised."
            return ctx

        # Default fallback
        ctx.policy_decision = "MANUAL_REVIEW_DENY"
        ctx.barrier_command = "LOCK_BARRIER"
        ctx.final_reason = "Access denied under general perimeter security guidelines."
        return ctx

    def get_summary(self, ctx: AccessContext) -> str:
        return f"DECISION: {ctx.policy_decision} -> Command: {ctx.barrier_command} ({ctx.final_reason})"
