from sqlalchemy.ext.asyncio import AsyncSession
from backend.ai_engine.base_agent import BaseAgent
from backend.ai_engine.context import AccessContext
from backend.models import Alert
from backend.services.websocket_manager import ws_manager

class NotificationAgent(BaseAgent):
    """
    AGENT 6: Notification Agent
    Dispatches real-time security alerts over WebSockets and logs active incidents.
    Coordinates incident response when anomalies or high-risk denials occur.
    """

    def __init__(self):
        super().__init__("Notification Agent")

    async def evaluate(self, ctx: AccessContext, db: AsyncSession) -> AccessContext:
        # Check if an alert notification must be raised
        if ctx.policy_decision == "MANUAL_REVIEW_DENY" or ctx.risk_level == "HIGH":
            severity = "HIGH" if (ctx.has_anomaly or ctx.identity_status == "SUSPENDED") else "MEDIUM"
            
            # Create Alert in persistence layer
            alert = Alert(
                severity=severity,
                gate_id=ctx.gate_id,
                user_identifier=f"{ctx.person_id or 'Unknown'} ({ctx.full_name or 'Unknown'})",
                reason=ctx.final_reason,
                action_required="On-duty security officer assigned for physical verification",
                status="ACTIVE",
                assigned_officer="Unassigned"
            )
            db.add(alert)
            await db.commit()
            await db.refresh(alert)

            ctx.alert_id = alert.alert_id
            ctx.notification_dispatched = True

            # Broadcast live alert to SOC Dashboard
            await ws_manager.broadcast("NEW_ALERT", {
                "alert_id": alert.alert_id,
                "severity": severity,
                "gate": ctx.gate_id,
                "subject": alert.user_identifier,
                "reason": ctx.final_reason,
                "timestamp": alert.timestamp.isoformat()
            })
        else:
            ctx.notification_dispatched = False

        return ctx

    def get_summary(self, ctx: AccessContext) -> str:
        if ctx.notification_dispatched:
            return f"DISPATCHED: High-Priority Alert #{ctx.alert_id} broadcast to SOC & Security Desk"
        return "PASSIVE: Standard telemetry logged, no incident alert required"
