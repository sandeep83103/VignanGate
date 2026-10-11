from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.ai_engine.base_agent import BaseAgent
from backend.ai_engine.context import AccessContext
from backend.models import Visitor

class AuthorizationAgent(BaseAgent):
    """
    AGENT 2: Authorization Agent
    Evaluates role-based access control (RBAC), gate policies, and time-of-day access windows.
    Enforces student curfew hours (post 21:00) and visitor pass validations.
    """

    def __init__(self):
        super().__init__("Authorization Agent")

    async def evaluate(self, ctx: AccessContext, db: AsyncSession) -> AccessContext:
        if ctx.identity_status != "VERIFIED":
            # If identity is unverified or suspended, cannot authorize
            ctx.auth_status = "UNAUTHORIZED"
            ctx.auth_reason = f"Cannot authorize unverified identity state ({ctx.identity_status})"
            return ctx

        hour = ctx.timestamp.hour
        role = ctx.role or "Student"
        gate = ctx.gate_id

        # 1. Faculty Policy: 24/7 Unrestricted Clearance across all gates
        if role == "Faculty":
            ctx.auth_status = "AUTHORIZED"
            ctx.auth_reason = "Faculty credential: 24/7 Unrestricted Campus Clearance"
            return ctx

        # 2. Student Policy: Schedule & Curfew Checks
        if role == "Student":
            # Hostel curfew window: 21:30 to 05:30
            if hour >= 22 or hour < 5:
                ctx.auth_status = "CURFEW_RESTRICTED"
                ctx.auth_reason = f"Curfew violation: Student entry attempted at {hour}:00 IST without warden pass"
                return ctx

            ctx.auth_status = "AUTHORIZED"
            ctx.auth_reason = f"Standard student daytime access authorized at {gate}"
            return ctx

        # 3. Visitor Policy: Check active visitor pass
        if role == "Visitor":
            stmt = select(Visitor).where(
                (Visitor.visitor_id == ctx.credential_id) | (Visitor.qr_hash == ctx.credential_id)
            )
            res = await db.execute(stmt)
            vis = res.scalars().first()

            if vis and vis.approval_status == "APPROVED":
                ctx.auth_status = "AUTHORIZED"
                ctx.auth_reason = f"Approved visitor pass: Hosted by {vis.host_name}"
            else:
                ctx.auth_status = "UNAUTHORIZED"
                ctx.auth_reason = "Visitor pass not found or unapproved by host department"
            return ctx

        # 4. Vendor Policy: 07:00 to 19:00 Delivery window
        if role == "Vendor":
            if 7 <= hour <= 19:
                ctx.auth_status = "AUTHORIZED"
                ctx.auth_reason = "Vendor delivery window active"
            else:
                ctx.auth_status = "ZONE_RESTRICTED"
                ctx.auth_reason = "Vendor deliveries prohibited outside 07:00-19:00 window"
            return ctx

        # Default fallback
        ctx.auth_status = "AUTHORIZED"
        ctx.auth_reason = f"Role '{role}' standard access approved"
        return ctx

    def get_summary(self, ctx: AccessContext) -> str:
        return f"{ctx.auth_status}: {ctx.auth_reason}"
