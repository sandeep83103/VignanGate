"""
==============================================================================
Unit & Integration Tests for Phase 4: Production Multi-Agent AI Engine
==============================================================================
"""

import pytest
import pytest_asyncio
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import engine, Base, AsyncSessionLocal
from backend.services.seed import seed_initial_data
from backend.ai_engine.context import AccessContext
from backend.ai_engine.pipeline import agentic_pipeline
from backend.ai_engine.agents.identity_agent import IdentityAgent
from backend.ai_engine.agents.authorization_agent import AuthorizationAgent
from backend.ai_engine.agents.risk_agent import RiskAgent
from backend.ai_engine.agents.anomaly_agent import AnomalyAgent
from backend.ai_engine.agents.policy_agent import PolicyAgent
from backend.ai_engine.agents.notification_agent import NotificationAgent
from backend.models import AccessLog

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_identity_agent_scenarios():
    agent = IdentityAgent()
    async with AsyncSessionLocal() as db:
        # 1. Valid Active Student
        ctx1 = AccessContext(gate_id="University Gate", credential_id="STU20261245")
        ctx1 = await agent.run(ctx1, db)
        assert ctx1.identity_status == "VERIFIED"
        assert ctx1.full_name == "Rahul Kumar"
        assert ctx1.role == "Student"

        # 2. Suspended Student
        ctx2 = AccessContext(gate_id="University Gate", credential_id="SUSP-STU-001")
        ctx2 = await agent.run(ctx2, db)
        assert ctx2.identity_status == "SUSPENDED"

        # 3. Unregistered Visitor UID
        ctx3 = AccessContext(gate_id="University Gate", credential_id="UNKNOWN_CARD_99")
        ctx3 = await agent.run(ctx3, db)
        assert ctx3.identity_status == "UNREGISTERED"


@pytest.mark.asyncio
async def test_authorization_agent_curfew_enforcement():
    auth_agent = AuthorizationAgent()
    async with AsyncSessionLocal() as db:
        # Daytime student access (14:00) -> AUTHORIZED
        day_ctx = AccessContext(
            gate_id="University Gate",
            credential_id="STU20261245",
            timestamp=datetime.datetime(2026, 10, 12, 14, 30, tzinfo=datetime.timezone.utc)
        )
        day_ctx.identity_status = "VERIFIED"
        day_ctx.role = "Student"
        day_ctx = await auth_agent.run(day_ctx, db)
        assert day_ctx.auth_status == "AUTHORIZED"

        # Night curfew student access (23:15) -> CURFEW_RESTRICTED
        night_ctx = AccessContext(
            gate_id="University Gate",
            credential_id="STU20261245",
            timestamp=datetime.datetime(2026, 10, 12, 23, 15, tzinfo=datetime.timezone.utc)
        )
        night_ctx.identity_status = "VERIFIED"
        night_ctx.role = "Student"
        night_ctx = await auth_agent.run(night_ctx, db)
        assert night_ctx.auth_status == "CURFEW_RESTRICTED"

        # Faculty at midnight (00:30) -> 24/7 AUTHORIZED
        fac_ctx = AccessContext(
            gate_id="University Gate",
            credential_id="FAC10421",
            timestamp=datetime.datetime(2026, 10, 12, 0, 30, tzinfo=datetime.timezone.utc)
        )
        fac_ctx.identity_status = "VERIFIED"
        fac_ctx.role = "Faculty"
        fac_ctx = await auth_agent.run(fac_ctx, db)
        assert fac_ctx.auth_status == "AUTHORIZED"


@pytest.mark.asyncio
async def test_anomaly_agent_anti_passback():
    from sqlalchemy import delete
    anomaly_agent = AnomalyAgent()
    async with AsyncSessionLocal() as db:
        # Clear any leftover logs for test user
        await db.execute(delete(AccessLog).where(AccessLog.person_id == "STU20261082"))
        await db.commit()

        # Record a prior entry access log 2 minutes ago
        two_mins_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=2)
        prior_log = AccessLog(
            timestamp=two_mins_ago,
            person_id="STU20261082",
            full_name="Ananya Reddy",
            user_type="Student",
            gate_id="University Gate",
            risk_level="LOW",
            decision="GRANTED",
            method="RFID"
        )
        db.add(prior_log)
        await db.commit()

        # Second entry tap 2 minutes later without recorded exit -> Anti-Passback detected!
        ctx = AccessContext(
            gate_id="University Gate",
            credential_id="STU20261082",
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        ctx.identity_status = "VERIFIED"
        ctx.person_id = "STU20261082"
        ctx.role = "Student"

        ctx = await anomaly_agent.run(ctx, db)
        assert ctx.has_anomaly is True
        assert any("ANTI_PASSBACK_VIOLATION" in flag for flag in ctx.anomaly_flags)
        assert ctx.risk_level == "HIGH"


@pytest.mark.asyncio
async def test_anomaly_agent_impossible_velocity():
    anomaly_agent = AnomalyAgent()
    async with AsyncSessionLocal() as db:
        # Record entry at University Gate 25 seconds ago
        just_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=25)
        log1 = AccessLog(
            timestamp=just_now,
            person_id="VELOCITY_TEST_USER",
            full_name="Velocity Test",
            user_type="Student",
            gate_id="University Gate",
            risk_level="LOW",
            decision="GRANTED",
            method="RFID"
        )
        db.add(log1)
        await db.commit()

        # Tap at Library Gate 25 seconds later (Physical travel requires >= 120s) -> Impossible Velocity!
        ctx = AccessContext(
            gate_id="Library Gate",
            credential_id="VELOCITY_TEST_USER",
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        ctx.identity_status = "VERIFIED"
        ctx.person_id = "VELOCITY_TEST_USER"
        ctx.role = "Student"

        ctx = await anomaly_agent.run(ctx, db)
        assert ctx.has_anomaly is True
        assert any("IMPOSSIBLE_VELOCITY" in flag for flag in ctx.anomaly_flags)


@pytest.mark.asyncio
async def test_full_pipeline_fast_lane_and_latency():
    async with AsyncSessionLocal() as db:
        ctx = AccessContext(
            gate_id="Lara Gate",
            credential_id="FAC10421", # Dr. Priya Rao
            method="RFID"
        )
        ctx = await agentic_pipeline.execute(ctx, db)

        # Confirm all 6 agents ran
        assert len(ctx.execution_trace) == 6
        agent_names = [s.agent_name for s in ctx.execution_trace]
        assert agent_names == [
            "Identity Agent",
            "Authorization Agent",
            "Risk Agent",
            "Anomaly Agent",
            "Policy Agent",
            "Notification Agent"
        ]

        # Verification result
        assert ctx.policy_decision == "FAST_LANE_GRANT"
        assert ctx.barrier_command == "OPEN_BARRIER"
        assert ctx.risk_level == "LOW"
        assert ctx.notification_dispatched is False

        # Benchmark Success Metric: Total decision time under 120ms
        assert ctx.total_pipeline_ms < 120.0, f"Pipeline latency too high: {ctx.total_pipeline_ms}ms"
