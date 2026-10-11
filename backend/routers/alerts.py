from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from backend.database import get_db
from backend.models import Alert
from backend.schemas import AlertResponse, AlertUpdate
from backend.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/alerts", tags=["Security Alerts"])

@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Lists security alerts with optional status filtering."""
    stmt = select(Alert).order_by(desc(Alert.timestamp))
    if status and status != "ALL":
        stmt = stmt.where(Alert.status == status)
    stmt = stmt.limit(limit)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: int, update_data: AlertUpdate, db: AsyncSession = Depends(get_db)):
    """Assigns security officer or resolves alert incident."""
    stmt = select(Alert).where(Alert.alert_id == alert_id)
    res = await db.execute(stmt)
    alert = res.scalars().first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert incident not found.")

    if update_data.status:
        alert.status = update_data.status
    if update_data.assigned_officer:
        alert.assigned_officer = update_data.assigned_officer

    await db.commit()
    await db.refresh(alert)

    # Broadcast update to connected dashboards
    await ws_manager.broadcast("ALERT_UPDATED", {
        "alert_id": alert.alert_id,
        "status": alert.status,
        "assigned": alert.assigned_officer
    })

    return alert
