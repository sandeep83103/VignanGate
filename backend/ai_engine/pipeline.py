import time
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from backend.ai_engine.context import AccessContext
from backend.ai_engine.agents.identity_agent import IdentityAgent
from backend.ai_engine.agents.authorization_agent import AuthorizationAgent
from backend.ai_engine.agents.risk_agent import RiskAgent
from backend.ai_engine.agents.anomaly_agent import AnomalyAgent
from backend.ai_engine.agents.policy_agent import PolicyAgent
from backend.ai_engine.agents.notification_agent import NotificationAgent

logger = logging.getLogger("vignan.ai_engine")

class AgenticPipeline:
    """
    Coordinated 6-Agent AI Decision Pipeline:
    1. Identity Agent
    2. Authorization Agent
    3. Risk Agent
    4. Anomaly Agent
    5. Policy Agent
    6. Notification Agent
    """

    def __init__(self):
        self.agents = [
            IdentityAgent(),
            AuthorizationAgent(),
            RiskAgent(),
            AnomalyAgent(),
            PolicyAgent(),
            NotificationAgent()
        ]

    async def execute(self, ctx: AccessContext, db: AsyncSession) -> AccessContext:
        start_time = time.perf_counter()

        for agent in self.agents:
            ctx = await agent.run(ctx, db)

        total_ms = round((time.perf_counter() - start_time) * 1000, 2)
        ctx.total_pipeline_ms = total_ms

        logger.info(
            f"[AI Pipeline] Gate: {ctx.gate_id} | Credential: {ctx.credential_id} | "
            f"Decision: {ctx.policy_decision} | Risk: {ctx.risk_score} | Latency: {total_ms}ms"
        )
        return ctx

agentic_pipeline = AgenticPipeline()
