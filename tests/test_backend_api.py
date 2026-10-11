"""
==============================================================================
Integration Tests for Phase 3: Cloud Ingestion, Messaging & Persistence
==============================================================================
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import app
from backend.database import engine, Base, AsyncSessionLocal
from backend.services.seed import seed_initial_data

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
async def test_list_gates():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/gates/")
        assert res.status_code == 200
        gates = res.json()
        assert len(gates) >= 3
        gate_names = [g["gate_name"] for g in gates]
        assert "University Gate" in gate_names
        assert "Lara Gate" in gate_names
        assert "Library Gate" in gate_names


@pytest.mark.asyncio
async def test_scan_valid_student():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "gate_id": "University Gate",
            "credential_id": "STU20261245",
            "method": "RFID",
            "user_type": "Student"
        }
        res = await client.post("/api/access/scan", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["decision"] == "GRANTED"
        assert data["risk_level"] == "LOW"
        assert data["barrier_command"] == "OPEN_BARRIER"
        assert data["full_name"] == "Rahul Kumar"


@pytest.mark.asyncio
async def test_anti_rebound_rejection():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "gate_id": "Lara Gate",
            "credential_id": "FAC10421",
            "method": "RFID",
            "user_type": "Faculty"
        }
        # First tap -> Success
        res1 = await client.post("/api/access/scan", json=payload)
        assert res1.status_code == 200
        assert res1.json()["decision"] == "GRANTED"

        # Immediate second tap within 1.5s -> HTTP 429 Anti-Rebound
        res2 = await client.post("/api/access/scan", json=payload)
        assert res2.status_code == 429
        assert "Anti-rebound reject" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_scan_unregistered_id_generates_alert():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "gate_id": "Library Gate",
            "credential_id": "SUSPICIOUS-UID-999",
            "method": "Manual",
            "user_type": "Visitor"
        }
        res = await client.post("/api/access/scan", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["decision"] == "DENIED"
        assert data["risk_level"] == "HIGH"
        assert data["barrier_command"] == "LOCK_BARRIER"

        # Check alert list
        alert_res = await client.get("/api/alerts/")
        assert alert_res.status_code == 200
        alerts = alert_res.json()
        assert any("SUSPICIOUS-UID-999" in a["user_identifier"] for a in alerts)


@pytest.mark.asyncio
async def test_visitor_registration_and_hash():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        visitor_payload = {
            "visitor_name": "S. K. Murthy",
            "mobile_number": "9949112233",
            "host_name": "Dr. Priya Rao",
            "purpose": "Academic Inspection",
            "gate_id": "University Gate"
        }
        res = await client.post("/api/visitors/", json=visitor_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["visitor_id"].startswith("VIS-2026-")
        assert len(data["qr_hash"]) == 32
        assert data["approval_status"] == "APPROVED"


@pytest.mark.asyncio
async def test_telemetry_heartbeat():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        hb_payload = {
            "device_id": "ESP32-UG-001",
            "gate": "University Gate",
            "status": "ONLINE",
            "signal_percent": 95,
            "barrier_state": "CLOSED",
            "tailgating_flag": False,
            "uptime_sec": 3600
        }
        res = await client.post("/api/telemetry/heartbeat", json=hb_payload)
        assert res.status_code == 200
        assert res.json()["status"] == "HEARTBEAT_ACK"


@pytest.mark.asyncio
async def test_csv_log_export():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/access/export")
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        content = res.text
        assert "Timestamp,Person ID,Full Name,User Type,Gate,Risk Level,Decision,Method,Reason" in content
        assert "STU20261245" in content


@pytest.mark.asyncio
async def test_alert_officer_assignment():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        alerts_res = await client.get("/api/alerts/?status=ACTIVE")
        alerts = alerts_res.json()
        assert len(alerts) > 0
        target_id = alerts[0]["alert_id"]

        patch_res = await client.patch(f"/api/alerts/{target_id}", json={
            "assigned_officer": "Inspector K. Sharma",
            "status": "ACTIVE"
        })
        assert patch_res.status_code == 200
        assert patch_res.json()["assigned_officer"] == "Inspector K. Sharma"

        # Resolve alert
        resolve_res = await client.patch(f"/api/alerts/{target_id}", json={
            "status": "RESOLVED"
        })
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "RESOLVED"
