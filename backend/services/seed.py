from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import datetime

from backend.models import Gate, Device, User, AccessLog, Alert

async def seed_initial_data(db: AsyncSession):
    """Populates the database with initial Vignan University gates, devices, and demo users."""

    # 1. Seed Gates
    gates_data = [
        {"gate_id": "GATE-UG-01", "gate_name": "University Gate", "location_code": "SEC-A-MAIN", "status": "ONLINE", "today_entries": 1284, "current_risk": "LOW"},
        {"gate_id": "GATE-LG-01", "gate_name": "Lara Gate", "location_code": "SEC-B-LARA", "status": "ONLINE", "today_entries": 936, "current_risk": "MEDIUM"},
        {"gate_id": "GATE-LIB-01", "gate_name": "Library Gate", "location_code": "SEC-C-LIB", "status": "ONLINE", "today_entries": 626, "current_risk": "LOW"}
    ]
    for g in gates_data:
        existing = await db.execute(select(Gate).where(Gate.gate_id == g["gate_id"]))
        if not existing.scalars().first():
            db.add(Gate(**g))

    # 2. Seed Users
    users_data = [
        {"person_id": "STU20261245", "full_name": "Rahul Kumar", "role": "Student", "department": "CSE", "rfid_uid": "A35F821B", "status": "ACTIVE"},
        {"person_id": "FAC10421", "full_name": "Dr. Priya Rao", "role": "Faculty", "department": "CSE", "rfid_uid": "C48A109E", "status": "ACTIVE"},
        {"person_id": "STU20261082", "full_name": "Ananya Reddy", "role": "Student", "department": "ECE", "rfid_uid": "D291FB33", "status": "ACTIVE"},
        {"person_id": "STU20261199", "full_name": "K. Teja", "role": "Student", "department": "Mechanical", "rfid_uid": "E912FA00", "status": "ACTIVE"},
        {"person_id": "SUSP-STU-001", "full_name": "Suspended User", "role": "Student", "department": "Civil", "rfid_uid": "88776655", "status": "SUSPENDED"}
    ]
    for u in users_data:
        existing = await db.execute(select(User).where(User.person_id == u["person_id"]))
        if not existing.scalars().first():
            db.add(User(**u))

    # 3. Seed Devices
    devices_data = [
        {"device_id": "ESP32-UG-001", "gate_id": "GATE-UG-01", "device_type": "ESP32 Controller", "status": "ONLINE", "signal_percent": 94},
        {"device_id": "RFID-UG-001", "gate_id": "GATE-UG-01", "device_type": "RFID Reader", "status": "ONLINE", "signal_percent": 91},
        {"device_id": "BAR-UG-001", "gate_id": "GATE-UG-01", "device_type": "Barrier Relay", "status": "ONLINE", "signal_percent": 96},
        {"device_id": "ESP32-LG-001", "gate_id": "GATE-LG-01", "device_type": "ESP32 Controller", "status": "ONLINE", "signal_percent": 87},
        {"device_id": "RFID-LG-001", "gate_id": "GATE-LG-01", "device_type": "RFID Reader", "status": "ONLINE", "signal_percent": 84},
        {"device_id": "ESP32-LIB-001", "gate_id": "GATE-LIB-01", "device_type": "ESP32 Controller", "status": "ONLINE", "signal_percent": 92},
        {"device_id": "RFID-LIB-001", "gate_id": "GATE-LIB-01", "device_type": "RFID Reader", "status": "ONLINE", "signal_percent": 88}
    ]
    for d in devices_data:
        existing = await db.execute(select(Device).where(Device.device_id == d["device_id"]))
        if not existing.scalars().first():
            db.add(Device(**d))

    # 4. Seed Alerts
    existing_alert = await db.execute(select(Alert))
    if not existing_alert.scalars().first():
        db.add(Alert(
            severity="HIGH",
            gate_id="Lara Gate",
            user_identifier="Unknown Visitor",
            reason="Invalid credential + no host authorization",
            action_required="Manual verification required",
            status="ACTIVE",
            assigned_officer="Unassigned"
        ))
        db.add(Alert(
            severity="MEDIUM",
            gate_id="University Gate",
            user_identifier="STU-DEMO-041",
            reason="Multiple rapid entry attempts (Anti-passback warning)",
            action_required="Review access pattern",
            status="ACTIVE",
            assigned_officer="Unassigned"
        ))

    await db.commit()
