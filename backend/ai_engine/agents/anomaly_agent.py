from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.ai_engine.base_agent import BaseAgent
from backend.ai_engine.context import AccessContext
from backend.models import AccessLog

# Campus Geographic Distance Transit Matrix (Minimum Travel Time in Seconds)
MIN_TRANSIT_SECONDS = {
    ("University Gate", "Lara Gate"): 90,
    ("Lara Gate", "University Gate"): 90,
    ("University Gate", "Library Gate"): 120,
    ("Library Gate", "University Gate"): 120,
    ("Lara Gate", "Library Gate"): 80,
    ("Library Gate", "Lara Gate"): 80
}

class AnomalyAgent(BaseAgent):
    """
    AGENT 4: Anomaly Agent
    Executes behavioral anomaly and fraud detection algorithms:
    1. Anti-Passback (APB): Detects duplicate entries without recorded exits.
    2. Geographic Velocity Check: Detects impossible travel speed across gates (Card Cloning / Sharing).
    3. Rapid Multi-Failure Pattern: Detects brute-force trial scans.
    """

    def __init__(self):
        super().__init__("Anomaly Agent")

    async def evaluate(self, ctx: AccessContext, db: AsyncSession) -> AccessContext:
        anomalies = []

        if not ctx.person_id or ctx.identity_status == "UNREGISTERED":
            # Unregistered cards have default base risk, anomaly focuses on registered credentials
            ctx.anomaly_flags = []
            ctx.has_anomaly = False
            return ctx

        # Fetch recent transactions for this person (last 4 hours)
        four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=4)
        stmt = (
            select(AccessLog)
            .where(
                (AccessLog.person_id == ctx.person_id) &
                (AccessLog.timestamp >= four_hours_ago)
            )
            .order_by(desc(AccessLog.timestamp))
            .limit(5)
        )
        res = await db.execute(stmt)
        recent_logs = res.scalars().all()

        if recent_logs:
            last_log = recent_logs[0]
            # Ensure timezone awareness for comparison
            last_ts = last_log.timestamp
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            
            curr_ts = ctx.timestamp
            if curr_ts.tzinfo is None:
                curr_ts = curr_ts.replace(tzinfo=timezone.utc)

            delta_seconds = abs((curr_ts - last_ts).total_seconds())

            # -------------------------------------------------------------
            # 1. Geographic Velocity / Impossible Travel Check
            # -------------------------------------------------------------
            if last_log.gate_id != ctx.gate_id:
                pair = (last_log.gate_id, ctx.gate_id)
                min_time = MIN_TRANSIT_SECONDS.get(pair, 60)
                if delta_seconds < min_time:
                    anomalies.append(
                        f"IMPOSSIBLE_VELOCITY (Transit from {last_log.gate_id} to {ctx.gate_id} in {int(delta_seconds)}s; required >= {min_time}s)"
                    )

            # -------------------------------------------------------------
            # 2. Anti-Passback (APB) Algorithm
            # -------------------------------------------------------------
            # If the user's last action was a GRANTED entry within 4 hours at the same or another gate,
            # and another entry is attempted without an exit event, flag Passback.
            if last_log.decision == "GRANTED" and delta_seconds < 14400: # 4 hours
                # If subsequent tap occurs within 10 minutes at any entry gate
                if delta_seconds < 600:
                    anomalies.append(
                        f"ANTI_PASSBACK_VIOLATION (Duplicate entry tap {int(delta_seconds)}s after prior granted access without exit)"
                    )

            # -------------------------------------------------------------
            # 3. Repeated Failure / Brute Force Pattern
            # -------------------------------------------------------------
            denials_count = sum(1 for l in recent_logs[:3] if l.decision != "GRANTED")
            if denials_count >= 2:
                anomalies.append("REPEATED_CREDENTIAL_FAILURES (Multiple consecutive denied taps)")

        ctx.anomaly_flags = anomalies
        ctx.has_anomaly = len(anomalies) > 0

        # If severe anomalies detected, escalate risk score
        if ctx.has_anomaly:
            ctx.risk_score = min(ctx.risk_score + 50.0, 100.0)
            ctx.risk_level = "HIGH"

        return ctx

    def get_summary(self, ctx: AccessContext) -> str:
        if not ctx.has_anomaly:
            return "CLEAN: No passback, velocity, or spoofing anomalies detected"
        return f"ANOMALY DETECTED: {'; '.join(ctx.anomaly_flags)}"
