import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List

from backend.database import get_db
from backend.models import Gate, Alert
from backend.schemas import BarrierCommand, EmergencyReleaseRequest, EmergencyResetRequest, EmergencyStatusResponse
from backend.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/gates", tags=["Perimeter Gates"])

@router.get("/")
async def list_gates(db: AsyncSession = Depends(get_db)):
    """Retrieves all monitored gates, current barrier states, and entry counts."""
    res = await db.execute(select(Gate))
    return res.scalars().all()

@router.get("/emergency-status", response_model=EmergencyStatusResponse)
async def get_emergency_status(db: AsyncSession = Depends(get_db)):
    """Checks whether an emergency evacuation is currently active across perimeter gates."""
    res = await db.execute(select(Gate))
    gates = res.scalars().all()
    
    emergency_gates = [g.gate_name for g in gates if g.barrier_state == "EMERGENCY_OPEN"]
    is_active = len(emergency_gates) > 0
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return EmergencyStatusResponse(
        status="EMERGENCY_EVACUATION_ACTIVE" if is_active else "SECURE_NORMAL",
        timestamp=now_str,
        active=is_active,
        gates_affected=emergency_gates,
        message="All perimeter gates are forced open for emergency egress." if is_active else "Perimeter access control operating under normal security profile."
    )

@router.post("/emergency-release")
async def trigger_emergency_release(
    req: EmergencyReleaseRequest = EmergencyReleaseRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    Hardware/Software Fire Alarm Interlock (GPIO 35):
    Immediately commands ALL perimeter gates to EMERGENCY_OPEN fail-safe state,
    dispatches critical campus-wide alerts, and broadcasts evacuation signal.
    """
    res = await db.execute(select(Gate))
    gates = res.scalars().all()
    gate_names = []

    for gate in gates:
        gate.barrier_state = "EMERGENCY_OPEN"
        gate_names.append(gate.gate_name)

    # Log critical system alert for audit trail
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    alert = Alert(
        timestamp=now_dt,
        severity="CRITICAL",
        gate_id="ALL_GATES",
        user_identifier=req.triggered_by or "FACP-INTERLOCK",
        reason=f"FIRE ALARM INTERLOCK ACTIVATED: {req.reason or 'Dry-contact trip on GPIO 35'}",
        action_required="Commence immediate campus perimeter evacuation protocol; all gates unlocked",
        status="ACTIVE",
        assigned_officer="Emergency Response Team (ERT)"
    )
    db.add(alert)
    await db.commit()

    # Real-time WebSocket evacuation broadcast
    await ws_manager.broadcast("EMERGENCY_EVACUATION_TRIGGERED", {
        "status": "EMERGENCY_EVACUATION_ACTIVE",
        "triggered_by": req.triggered_by,
        "reason": req.reason,
        "gates_affected": gate_names,
        "timestamp": now_dt.isoformat()
    })

    return {
        "status": "EMERGENCY_EVACUATION_ACTIVATED",
        "message": "Failsafe interlock engaged. All perimeter gates released to EMERGENCY_OPEN.",
        "triggered_by": req.triggered_by,
        "reason": req.reason,
        "gates_affected": gate_names,
        "timestamp": now_dt.isoformat()
    }

@router.post("/emergency-reset")
async def reset_emergency_release(
    req: EmergencyResetRequest = EmergencyResetRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    Authoritative reset of fire evacuation mode by security supervisor.
    Restores all perimeter gates to secure CLOSED state.
    """
    res = await db.execute(select(Gate))
    gates = res.scalars().all()
    gate_names = []

    for gate in gates:
        gate.barrier_state = "CLOSED"
        gate_names.append(gate.gate_name)

    # Resolve active emergency alerts
    alert_stmt = select(Alert).where(Alert.gate_id == "ALL_GATES", Alert.status == "ACTIVE")
    alert_res = await db.execute(alert_stmt)
    for alert in alert_res.scalars().all():
        alert.status = "RESOLVED"
        alert.assigned_officer = req.officer_id

    await db.commit()

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    # Broadcast reset to SOC and edge gates
    await ws_manager.broadcast("EMERGENCY_EVACUATION_RESET", {
        "status": "SECURE_OPERATIONS_RESTORED",
        "officer": req.officer_id,
        "notes": req.notes,
        "gates_affected": gate_names,
        "timestamp": now_dt.isoformat()
    })

    return {
        "status": "SECURE_OPERATIONS_RESTORED",
        "message": "Emergency evacuation mode terminated. All perimeter barriers secured.",
        "officer_id": req.officer_id,
        "gates_affected": gate_names,
        "timestamp": now_dt.isoformat()
    }

@router.post("/command")
async def trigger_barrier_command(cmd: BarrierCommand, db: AsyncSession = Depends(get_db)):
    """Issues remote manual barrier commands from SOC to edge gate controller."""
    stmt = select(Gate).where(Gate.gate_name == cmd.gate_id)
    res = await db.execute(stmt)
    gate = res.scalars().first()

    if not gate:
        raise HTTPException(status_code=404, detail=f"Gate '{cmd.gate_id}' not found.")

    if cmd.action == "OPEN_BARRIER":
        gate.barrier_state = "OPEN"
    elif cmd.action == "LOCK_BARRIER":
        gate.barrier_state = "LOCKED"
    else:
        gate.barrier_state = "CLOSED"

    await db.commit()

    # Broadcast remote barrier actuation over WebSockets
    await ws_manager.broadcast("BARRIER_OVERRIDE", {
        "gate": cmd.gate_id,
        "action": cmd.action,
        "officer": cmd.officer_id
    })

    return {
        "status": "COMMAND_DISPATCHED",
        "gate_id": cmd.gate_id,
        "action": cmd.action,
        "new_barrier_state": gate.barrier_state
    }
