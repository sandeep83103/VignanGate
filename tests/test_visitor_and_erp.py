"""
==============================================================================
Integration Tests for Phase 5: Visitor Management & Institutional ERP Sync
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
from backend.services.visitor_service import visitor_service

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
async def test_visitor_lifecycle_and_token_signing():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Visitor Pre-registration
        reg_payload = {
            "visitor_name": "Prof. N. K. Sinha",
            "mobile_number": "9848112233",
            "host_name": "Dr. Priya Rao",
            "purpose": "Doctoral Defense Committee",
            "gate_id": "University Gate"
        }
        res = await client.post("/api/visitors/", json=reg_payload)
        assert res.status_code == 200
        visitor_data = res.json()
        vid = visitor_data["visitor_id"]
        assert vid.startswith("VIS-2026-")

        # 2. Host Approval Action
        action_res = await client.post(f"/api/visitors/{vid}/action", json={
            "action": "APPROVE",
            "reason": "Host approved doctoral committee entry"
        })
        assert action_res.status_code == 200
        assert action_res.json()["approval_status"] == "APPROVED"

        # 3. Verify Cryptographic Token & Tamper Evidence
        get_res = await client.get(f"/api/visitors/{vid}")
        assert get_res.status_code == 200
        token = get_res.json()["qr_hash"] # or signed_token from DB

        # Test token validation via VisitorService
        sample_token = visitor_service.generate_signed_token(vid, "Prof. N. K. Sinha", "Dr. Priya Rao", "University Gate")
        is_valid, payload, err = visitor_service.verify_token(sample_token)
        assert is_valid is True
        assert payload["vid"] == vid

        # Tampered Token Test (corrupt one byte in payload)
        corrupted_token = "A" + sample_token[1:]
        is_corrupt_valid, _, err_corrupt = visitor_service.verify_token(corrupted_token)
        assert is_corrupt_valid is False
        assert "signature verification failed" in err_corrupt.lower()


@pytest.mark.asyncio
async def test_qr_png_image_generation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register visitor
        res = await client.post("/api/visitors/", json={
            "visitor_name": "QR Image Test Visitor",
            "mobile_number": "9000100020",
            "host_name": "CSE Department",
            "purpose": "Campus Visit",
            "gate_id": "Lara Gate"
        })
        vid = res.json()["visitor_id"]

        # Fetch PNG QR Image
        img_res = await client.get(f"/api/visitors/{vid}/qr-image")
        assert img_res.status_code == 200
        assert img_res.headers["content-type"] == "image/png"
        # Validate PNG magic bytes \x89PNG
        assert img_res.content.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_optical_gate_qr_scanner_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and generate valid signed token
        token = visitor_service.generate_signed_token("VIS-2026-TEST", "Dr. Guest Speaker", "Dr. Priya Rao", "University Gate")

        # Scan valid QR at gate camera
        scan_res = await client.post("/api/visitors/verify-qr", json={
            "gate_id": "University Gate",
            "qr_token": token
        })
        assert scan_res.status_code == 200
        scan_data = scan_res.json()
        assert scan_data["method"] == "QR Pass"

        # Scan tampered / invalid QR at gate camera
        bad_scan_res = await client.post("/api/visitors/verify-qr", json={
            "gate_id": "University Gate",
            "qr_token": "INVALID_TAMPERED_TOKEN_XYZ"
        })
        assert bad_scan_res.status_code == 200
        bad_data = bad_scan_res.json()
        assert bad_data["decision"] == "DENIED"


@pytest.mark.asyncio
async def test_erp_delta_sync_and_credential_updates():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Trigger ERP delta sync
        sync_res = await client.post("/api/erp/sync")
        assert sync_res.status_code == 200
        sync_data = sync_res.json()
        assert sync_data["status"] == "SYNC_SUCCESSFUL"
        assert sync_data["records_processed"] >= 4
        assert sync_data["records_added"] >= 2
        assert sync_data["records_suspended"] >= 1
        # Success Metric: SLA under 2 minutes (120,000ms)
        assert sync_data["duration_ms"] < 120000

        # Verify that newly enrolled student STU20261401 can now scan through access endpoint
        scan_new_stu = await client.post("/api/access/scan", json={
            "gate_id": "University Gate",
            "credential_id": "STU20261401", # Newly synced in batch
            "method": "RFID"
        })
        assert scan_new_stu.status_code == 200
        assert scan_new_stu.json()["decision"] == "GRANTED"
        assert scan_new_stu.json()["full_name"] == "V. Sai Krishna"

        # Verify that suspended student STU20261199 is now DENIED
        scan_susp = await client.post("/api/access/scan", json={
            "gate_id": "University Gate",
            "credential_id": "STU20261199", # Suspended in batch
            "method": "RFID"
        })
        assert scan_susp.status_code == 200
        assert scan_susp.json()["decision"] == "DENIED"
        assert scan_susp.json()["risk_level"] == "HIGH"


@pytest.mark.asyncio
async def test_erp_status_and_bulk_import():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Check ERP Status
        status_res = await client.get("/api/erp/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["total_credentials"] > 5
        assert status_data["active_credentials"] >= 4
        assert status_data["last_sync_status"] == "COMPLETED"

        # Bulk Import Test
        bulk_payload = [
            {
                "person_id": "FAC10999",
                "full_name": "Dr. Visiting Scientist",
                "role": "Faculty",
                "department": "Nanotechnology",
                "rfid_uid": "NANO9999",
                "status": "ACTIVE"
            }
        ]
        bulk_res = await client.post("/api/erp/bulk-import", json=bulk_payload)
        assert bulk_res.status_code == 200
        assert bulk_res.json()["total_imported"] == 1
