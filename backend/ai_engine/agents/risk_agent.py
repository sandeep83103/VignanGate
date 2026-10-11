from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.ai_engine.base_agent import BaseAgent
from backend.ai_engine.context import AccessContext
from backend.models import AccessLog

class RiskAgent(BaseAgent):
    """
    AGENT 3: Risk Agent
    Computes a multi-factor quantitative risk score (0.0 to 100.0).
    Synthesizes identity status, gate risk profiles, off-hour factors, and historical incident history.
    """

    def __init__(self):
        super().__init__("Risk Agent")

    async def evaluate(self, ctx: AccessContext, db: AsyncSession) -> AccessContext:
        score = 0.0
        factors = []

        # Factor 1: Identity & Role Base Score
        if ctx.identity_status == "SUSPENDED":
            score += 85.0
            factors.append("Suspended Account Flag (+85)")
        elif ctx.identity_status == "UNREGISTERED":
            score += 65.0
            factors.append("Unregistered Credential UID (+65)")
        elif ctx.role == "Visitor":
            score += 20.0
            factors.append("External Visitor (+20)")
        elif ctx.role == "Student":
            score += 5.0
        elif ctx.role == "Faculty":
            score += 0.0

        # Factor 2: Authorization State Modifier
        if ctx.auth_status == "CURFEW_RESTRICTED":
            score += 40.0
            factors.append("Curfew Restriction (+40)")
        elif ctx.auth_status == "UNAUTHORIZED":
            score += 35.0
            factors.append("Authorization Failure (+35)")

        # Factor 3: Time of Day Modifier
        hour = ctx.timestamp.hour
        if 23 <= hour or hour <= 4:
            score += 15.0
            factors.append("Late Night Hours (+15)")

        # Factor 4: Historical Violation Penalty (Last 24 Hours)
        if ctx.person_id:
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            stmt = select(func.count(AccessLog.log_id)).where(
                (AccessLog.person_id == ctx.person_id) &
                (AccessLog.decision != "GRANTED") &
                (AccessLog.timestamp >= since)
            )
            res = await db.execute(stmt)
            prior_denials = res.scalar() or 0
            if prior_denials > 0:
                penalty = min(prior_denials * 20.0, 40.0)
                score += penalty
                factors.append(f"{prior_denials} Prior Denials in 24h (+{penalty})")

        # Clamp score between 0.0 and 100.0
        final_score = min(max(score, 0.0), 100.0)
        ctx.risk_score = round(final_score, 1)
        ctx.risk_factors = factors

        if ctx.risk_score <= 25.0:
            ctx.risk_level = "LOW"
        elif ctx.risk_score <= 65.0:
            ctx.risk_level = "MEDIUM"
        else:
            ctx.risk_level = "HIGH"

        return ctx

    def get_summary(self, ctx: AccessContext) -> str:
        factor_str = ", ".join(ctx.risk_factors) if ctx.risk_factors else "Clean Baseline Profile"
        return f"{ctx.risk_level} RISK ({ctx.risk_score}/100) — {factor_str}"
