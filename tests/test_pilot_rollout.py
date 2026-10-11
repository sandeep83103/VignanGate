"""
==============================================================================
VIGNAN SMART ACCESS — PHASE 6 PILOT ROLLOUT & DEPLOYMENT TEST SUITE
Tests fire alarm emergency interlock, failsafe barrier release/reset,
30-day reliability audit calculation, gate deployment profiles,
and peak rush-hour load simulation.
==============================================================================
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.database import Base, get_db
from backend.app import app
from backend.services.seed import seed_initial_data
from backend.models import Gate, Alert
from tools.edge_simulator import ESP32GateController
from sqlalchemy.pool import StaticPool
from tools.load_stress_tester import LoadStressTester

TEST_DB_URL = "sqlite+aiosqlite:///file:test_pilot_mem?mode=memory&cache=shared&uri=true"

@pytest_asyncio.fixture
async def async_client():
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False, "uri": True},
        poolclass=StaticPool,
        echo=False
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        await seed_initial_data(session)

    async def override_get_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_emergency_fire_alarm_interlock_release_and_reset(async_client: AsyncClient):
    """
    Validates physical fire alarm interlock (GPIO 35):
    1. Triggers emergency evacuation -> all gates forced to EMERGENCY_OPEN.
    2. Critical system alert created.
    3. Status check confirms emergency evacuation is active.
    4. Authoritative reset restores barriers to CLOSED and resolves alerts.
    """
    # 1. Trigger Emergency Evacuation
    evac_payload = {
        "triggered_by": "FACP-ZONE-3-LIBRARY",
        "reason": "Optical Smoke Sensor Trip in Server Room"
    }
    resp = await async_client.post("/api/gates/emergency-release", json=evac_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "EMERGENCY_EVACUATION_ACTIVATED"
    assert len(data["gates_affected"]) >= 3

    # 2. Verify emergency status endpoint
    status_resp = await async_client.get("/api/gates/emergency-status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["active"] is True
    assert status_data["status"] == "EMERGENCY_EVACUATION_ACTIVE"
    assert "Library Gate" in status_data["gates_affected"]
    assert "University Gate" in status_data["gates_affected"]
    assert "Lara Gate" in status_data["gates_affected"]

    # 3. Verify gate barrier states in DB
    gates_resp = await async_client.get("/api/gates/")
    gates = gates_resp.json()
    for g in gates:
        assert g["barrier_state"] == "EMERGENCY_OPEN"

    # 4. Verify critical alert was generated
    alerts_resp = await async_client.get("/api/alerts/")
    alerts = alerts_resp.json()
    fire_alert = next((a for a in alerts if "FIRE ALARM INTERLOCK" in a["reason"]), None)
    assert fire_alert is not None
    assert fire_alert["severity"] == "CRITICAL"
    assert fire_alert["status"] == "ACTIVE"

    # 5. Authoritative Reset by Chief Security Officer
    reset_payload = {
        "officer_id": "CHIEF_SECURITY_VARMA",
        "notes": "Drill completed. All zones clear."
    }
    reset_resp = await async_client.post("/api/gates/emergency-reset", json=reset_payload)
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()
    assert reset_data["status"] == "SECURE_OPERATIONS_RESTORED"

    # 6. Verify status restored to normal
    post_status_resp = await async_client.get("/api/gates/emergency-status")
    post_status_data = post_status_resp.json()
    assert post_status_data["active"] is False
    assert post_status_data["status"] == "SECURE_NORMAL"

    # 7. Verify barriers returned to CLOSED
    gates_after_resp = await async_client.get("/api/gates/")
    for g in gates_after_resp.json():
        assert g["barrier_state"] == "CLOSED"


@pytest.mark.asyncio
async def test_edge_simulator_fire_alarm_interlock():
    """Validates the hardware edge emulator fire alarm interrupt and state machine."""
    edge = ESP32GateController("LIB-01", "Library Gate")
    assert edge.emergency_mode is False
    assert edge.barrier_open is False

    # Trigger fire interlock on GPIO 35
    trip_res = edge.trigger_fire_alarm(True)
    assert trip_res["action"] == "FAILSAFE_EVACUATION_TRIGGERED"
    assert trip_res["barrier_state"] == "EMERGENCY_OPEN"
    assert trip_res["gpio_pin"] == 35
    assert edge.emergency_mode is True

    # Telemetry should reflect emergency evacuation
    heartbeat = edge.generate_heartbeat()
    assert heartbeat["emergency_evacuation"] is True
    assert heartbeat["barrier_state"] == "EMERGENCY_OPEN"

    # Card tap during emergency should grant free egress
    tap_res = edge.simulate_rfid_tap("ANY_CARD")
    assert tap_res["decision"] == "GRANTED_EVACUATION"
    assert tap_res["mode"] == "EMERGENCY_EVACUATION"

    # Reset fire interlock
    reset_res = edge.trigger_fire_alarm(False)
    assert reset_res["action"] == "FAILSAFE_EVACUATION_RESET"
    assert edge.emergency_mode is False


@pytest.mark.asyncio
async def test_30_day_uptime_reliability_audit(async_client: AsyncClient):
    """
    Validates Phase 6 success criteria:
    Uptime reliability must exceed 99.9% over a 30-day testing window.
    """
    resp = await async_client.get("/api/telemetry/uptime")
    assert resp.status_code == 200
    data = resp.json()

    assert data["audit_window"]["duration_days"] == 30
    assert "campus_aggregate" in data

    agg = data["campus_aggregate"]
    assert agg["aggregate_uptime_percentage"] >= 99.90
    assert agg["compliance_status"] == "CERTIFIED_COMPLIANT"
    assert "GPIO 35" in agg["fire_interlock_readiness"]

    # Verify each gate meets SLA
    assert len(data["gate_details"]) >= 3
    for gate_info in data["gate_details"]:
        assert gate_info["uptime_percentage_30d"] >= 99.90
        assert gate_info["sla_compliant"] is True
        assert gate_info["mtbf_hours"] > 200.0


@pytest.mark.asyncio
async def test_gate_profiles_and_hardware_diagnostics(async_client: AsyncClient):
    """Validates retrieval of physical gate deployment specs and edge diagnostics."""
    # 1. Gate Profiles
    profiles_resp = await async_client.get("/api/telemetry/gate-profiles")
    assert profiles_resp.status_code == 200
    profiles = profiles_resp.json()
    assert "campus" in profiles
    assert len(profiles["gates"]) == 3

    # Check Library Gate (Pilot)
    lib_gate = next((g for g in profiles["gates"] if g["gate_id"] == "GATE-LIB-01"), None)
    assert lib_gate is not None
    assert lib_gate["hardware_sensors"]["emergency_pin"] == "GPIO 35 (Active-LOW Dry Contact Interlock)"
    assert lib_gate["pilot_details"]["duration_days"] == 14

    # 2. Hardware Diagnostics
    diag_resp = await async_client.get("/api/telemetry/diagnostics")
    assert diag_resp.status_code == 200
    diag = diag_resp.json()
    assert diag["system_status"] in ("NORMAL_OPERATIONAL", "CRITICAL_EVACUATION")
    assert diag["health_score_pct"] >= 0.0


@pytest.mark.asyncio
async def test_morning_rush_load_stress_simulation(async_client: AsyncClient):
    """
    Executes concurrent peak load simulation using the load stress tester.
    Validates response latency < 200 ms and throughput benchmark.
    """
    tester = LoadStressTester(client=async_client)
    metrics = await tester.execute_rush_simulation(
        total_requests=25,
        concurrency=5,
        target_lanes=7
    )

    assert metrics["total_requests"] == 25
    assert metrics["elapsed_seconds"] > 0
    assert metrics["decisions"]["granted"] > 0

    # Latency check: average latency should be under 200 ms
    avg_latency = metrics["latency_percentiles_ms"]["avg"]
    assert avg_latency < 200.0, f"Average latency {avg_latency} ms exceeded 200 ms target"
    assert metrics["latency_percentiles_ms"]["latency_benchmark_passed"] is True
