from abc import ABC, abstractmethod
import time
from sqlalchemy.ext.asyncio import AsyncSession
from backend.ai_engine.context import AccessContext, AgentTraceStep

class BaseAgent(ABC):
    """Abstract base class for all autonomous security micro-agents."""

    def __init__(self, name: str):
        self.name = name

    async def run(self, ctx: AccessContext, db: AsyncSession) -> AccessContext:
        """Executes the agent with microsecond timing and execution trace recording."""
        start_time = time.perf_counter()
        try:
            ctx = await self.evaluate(ctx, db)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            
            ctx.execution_trace.append(AgentTraceStep(
                agent_name=self.name,
                status="COMPLETED",
                duration_ms=elapsed_ms,
                output_summary=self.get_summary(ctx)
            ))
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            ctx.execution_trace.append(AgentTraceStep(
                agent_name=self.name,
                status="FAILED",
                duration_ms=elapsed_ms,
                output_summary=f"Error in {self.name}: {str(e)}"
            ))
            raise e
        return ctx

    @abstractmethod
    async def evaluate(self, ctx: AccessContext, db: AsyncSession) -> AccessContext:
        """Agent-specific reasoning and evaluation logic."""
        pass

    @abstractmethod
    def get_summary(self, ctx: AccessContext) -> str:
        """Returns concise single-line summary of agent's conclusion."""
        pass
