import time
import datetime
from typing import Dict, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from backend.config import settings
from backend.models import Gate, AccessLog
from backend.schemas import ScanRequest, ScanResponse, AgentTraceItem
from backend.services.websocket_manager import ws_manager
from backend.ai_engine.context import AccessContext
from backend.ai_engine.pipeline import agentic_pipeline

class IngestionService:
    def __init__(self):
        # In-memory anti-rebound tracking: (gate_id, credential_id) -> last_tap_time
        self._tap_history: Dict[Tuple[str, str], float] = {}

    def check_anti_rebound(self, gate_id: str, credential_id: str) -> None:
        """Enforces anti-rebound rate limiting (blocks duplicate taps within 1.5 seconds)."""
        key = (gate_id, credential_id.upper())
        now = time.time()
        last_tap = self._tap_history.get(key, 0)

        if now - last_tap < settings.ANTI_REBOUND_SECONDS:
            raise HTTPException(
                status_code=429,
                detail=f"Anti-rebound reject: Duplicate tap on gate '{gate_id}' within {settings.ANTI_REBOUND_SECONDS}s window."
            )
        self._tap_history[key] = now

    async def process_scan(self, req: ScanRequest, db: AsyncSession) -> ScanResponse:
        cred = req.credential_id.strip()
        self.check_anti_rebound(req.gate_id, cred)

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_str = now_dt.strftime("%H:%M:%S")

        # Initialize Multi-Agent Pipeline Context
        ctx = AccessContext(
            gate_id=req.gate_id,
            credential_id=cred,
            method=req.method,
            user_type=req.user_type,
            timestamp=now_dt
        )

        # Execute the Coordinated 6-Agent AI Engine
        ctx = await agentic_pipeline.execute(ctx, db)

        # Map Policy Decision to Standard Verdict
        if ctx.policy_decision == "FAST_LANE_GRANT":
            decision = "GRANTED"
            barrier_command = "OPEN_BARRIER"
            # Increment Gate entry counter
            gate_stmt = select(Gate).where(Gate.gate_name == req.gate_id)
            gate_res = await db.execute(gate_stmt)
            gate_obj = gate_res.scalars().first()
            if gate_obj:
                gate_obj.today_entries += 1
                await db.commit()
        elif ctx.policy_decision == "STANDARD_INSPECT":
            decision = "MANUAL REVIEW"
            barrier_command = "HOLD_CLOSED"
        else:
            decision = "DENIED"
            barrier_command = "LOCK_BARRIER"

        person_id = ctx.person_id or cred
        full_name = ctx.full_name or "Unknown Subject"
        user_type = ctx.role or req.user_type or "Visitor"
        reason = ctx.final_reason

        # Persist immutable AccessLog
        log = AccessLog(
            timestamp=now_dt,
            person_id=person_id,
            full_name=full_name,
            user_type=user_type,
            gate_id=req.gate_id,
            risk_level=ctx.risk_level,
            decision=decision,
            method=req.method,
            reason=reason
        )
        db.add(log)
        await db.commit()

        # Format trace items for response and live dashboard
        trace_items = [
            AgentTraceItem(
                agent_name=step.agent_name,
                status=step.status,
                duration_ms=step.duration_ms,
                output_summary=step.output_summary
            ) for step in ctx.execution_trace
        ]

        # Broadcast live scan event with full multi-agent breakdown to SOC Dashboards
        await ws_manager.broadcast("SCAN_EVENT", {
            "timestamp": now_str,
            "person_id": person_id,
            "full_name": full_name,
            "user_type": user_type,
            "gate": req.gate_id,
            "risk": ctx.risk_level,
            "risk_score": ctx.risk_score,
            "decision": decision,
            "method": req.method,
            "reason": reason,
            "anomalies": ctx.anomaly_flags,
            "pipeline_ms": ctx.total_pipeline_ms,
            "agent_trace": [t.model_dump() for t in trace_items]
        })

        return ScanResponse(
            decision=decision,
            person_id=person_id,
            full_name=full_name,
            user_type=user_type,
            gate_id=req.gate_id,
            risk_level=ctx.risk_level,
            risk_score=ctx.risk_score,
            barrier_command=barrier_command,
            reason=reason,
            timestamp=now_str,
            method=req.method,
            anomaly_flags=ctx.anomaly_flags,
            agent_trace=trace_items,
            pipeline_latency_ms=ctx.total_pipeline_ms
        )

ingestion_service = IngestionService()
