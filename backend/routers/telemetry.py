import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.database import get_db
from backend.models import Device, Gate
from backend.schemas import TelemetryPayload
from backend.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/telemetry", tags=["IoT Telemetry"])

@router.post("/heartbeat")
async def receive_heartbeat(data: TelemetryPayload, db: AsyncSession = Depends(get_db)):
    """Receives periodic MQTT / HTTP heartbeats from ESP32 controllers."""
    stmt = select(Device).where(Device.device_id == data.device_id)
    res = await db.execute(stmt)
    device = res.scalars().first()

    now_dt = datetime.datetime.now(datetime.timezone.utc)

    if device:
        device.status = data.status
        device.signal_percent = data.signal_percent
        device.last_heartbeat = now_dt
    else:
        # Register new device dynamically
        device = Device(
            device_id=data.device_id,
            gate_id=data.gate,
            device_type="ESP32 Controller",
            status=data.status,
            signal_percent=data.signal_percent,
            last_heartbeat=now_dt
        )
        db.add(device)

    # Update gate barrier state if included
    gate_stmt = select(Gate).where(Gate.gate_name == data.gate)
    gate_res = await db.execute(gate_stmt)
    gate_obj = gate_res.scalars().first()
    if gate_obj:
        gate_obj.barrier_state = data.barrier_state
        gate_obj.status = data.status

    await db.commit()

    # Forward telemetry to SOC dashboards via WebSocket
    await ws_manager.broadcast("TELEMETRY_UPDATE", {
        "device_id": data.device_id,
        "gate": data.gate,
        "status": data.status,
        "signal_percent": data.signal_percent,
        "barrier_state": data.barrier_state,
        "tailgating_flag": data.tailgating_flag,
        "emergency_evacuation": data.emergency_evacuation
    })

    return {
        "status": "HEARTBEAT_ACK",
        "device_id": data.device_id,
        "server_time": now_dt.isoformat()
    }

@router.get("/uptime")
async def get_uptime_audit(db: AsyncSession = Depends(get_db)):
    """Calculates continuous 30-day availability, MTBF, and SLA compliance (Phase 6 target >= 99.9%)."""
    from backend.services.uptime_service import UptimeService
    return await UptimeService.get_30_day_uptime_report(db)

@router.get("/gate-profiles")
async def get_gate_profiles():
    """Retrieves physical hardware deployment specifications and pinouts for all perimeter gates."""
    import os, json
    profiles_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "deployment", "gate_profiles.json")
    if os.path.exists(profiles_path):
        with open(profiles_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "gate_profiles.json not found"}

@router.get("/diagnostics")
async def get_diagnostics(db: AsyncSession = Depends(get_db)):
    """Performs instant perimeter health diagnostics across all connected edge microcontrollers."""
    stmt = select(Device)
    res = await db.execute(stmt)
    devices = res.scalars().all()

    gate_stmt = select(Gate)
    gate_res = await db.execute(gate_stmt)
    gates = gate_res.scalars().all()

    online_devices = sum(1 for d in devices if d.status == "ONLINE")
    emergency_gates = [g.gate_name for g in gates if g.barrier_state == "EMERGENCY_OPEN"]

    return {
        "system_status": "CRITICAL_EVACUATION" if emergency_gates else "NORMAL_OPERATIONAL",
        "total_monitored_devices": len(devices),
        "online_devices": online_devices,
        "health_score_pct": round((online_devices / max(len(devices), 1)) * 100, 1),
        "emergency_evacuation_active": len(emergency_gates) > 0,
        "emergency_gates": emergency_gates,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

