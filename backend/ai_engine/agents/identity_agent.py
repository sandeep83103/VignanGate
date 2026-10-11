from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.ai_engine.base_agent import BaseAgent
from backend.ai_engine.context import AccessContext
from backend.models import User

class IdentityAgent(BaseAgent):
    """
    AGENT 1: Identity Agent
    Validates physical RFID UID / Person ID against Vignan University's central registry.
    Checks UID syntax, account validity, and suspension flags.
    """

    def __init__(self):
        super().__init__("Identity Agent")

    async def evaluate(self, ctx: AccessContext, db: AsyncSession) -> AccessContext:
        cred = ctx.credential_id.strip()

        # Syntax check
        if len(cred) < 4:
            ctx.identity_status = "MALFORMED"
            ctx.full_name = "Invalid Credential"
            return ctx

        # Query user in institutional database
        stmt = select(User).where(
            (User.person_id == cred) | (User.rfid_uid == cred.upper())
        )
        res = await db.execute(stmt)
        user = res.scalars().first()

        if user:
            ctx.user = user
            ctx.person_id = user.person_id
            ctx.full_name = user.full_name
            ctx.role = user.role

            if user.status == "ACTIVE":
                ctx.identity_status = "VERIFIED"
            elif user.status == "SUSPENDED":
                ctx.identity_status = "SUSPENDED"
            else:
                ctx.identity_status = "EXPIRED"
        else:
            ctx.identity_status = "UNREGISTERED"
            ctx.person_id = cred
            ctx.full_name = "Unregistered Person"
            ctx.role = ctx.user_type or "Visitor"

        return ctx

    def get_summary(self, ctx: AccessContext) -> str:
        if ctx.identity_status == "VERIFIED":
            return f"MATCH: {ctx.person_id} -> {ctx.full_name} ({ctx.role})"
        elif ctx.identity_status == "SUSPENDED":
            return f"ALERT: Account {ctx.person_id} is SUSPENDED"
        elif ctx.identity_status == "MALFORMED":
            return f"REJECT: Malformed UID syntax ({ctx.credential_id})"
        return f"UNREGISTERED: No record found for UID {ctx.credential_id}"
