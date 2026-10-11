from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from backend.database import get_db
from backend.models import Gate
from backend.schemas import BarrierCommand
from backend.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/gates", tags=["Perimeter Gates"])

@router.get("/")
async def list_gates(db: AsyncSession = Depends(get_db)):
    """Retrieves all monitored gates, current barrier states, and entry counts."""
    res = await db.execute(select(Gate))
    return res.scalars().all()

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
