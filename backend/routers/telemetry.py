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
        "tailgating_flag": data.tailgating_flag
    })

    return {
        "status": "HEARTBEAT_ACK",
        "device_id": data.device_id,
        "server_time": now_dt.isoformat()
    }
