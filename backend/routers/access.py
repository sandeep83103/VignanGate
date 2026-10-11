from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
import io
import csv

from backend.database import get_db
from backend.models import AccessLog
from backend.schemas import ScanRequest, ScanResponse, AccessLogResponse
from backend.services.ingestion import ingestion_service

router = APIRouter(prefix="/api/access", tags=["Access Control"])

@router.post("/scan", response_model=ScanResponse)
async def scan_credential(req: ScanRequest, db: AsyncSession = Depends(get_db)):
    """Receives card tap from edge reader or optical scanner and runs verification."""
    return await ingestion_service.process_scan(req, db)

@router.get("/logs", response_model=List[AccessLogResponse])
async def get_access_logs(
    gate: Optional[str] = Query(None),
    user_type: Optional[str] = Query(None),
    risk: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves access logs with optional filtering."""
    stmt = select(AccessLog).order_by(desc(AccessLog.timestamp))
    if gate and gate != "All Gates":
        stmt = stmt.where(AccessLog.gate_id == gate)
    if user_type and user_type != "All Types":
        stmt = stmt.where(AccessLog.user_type == user_type)
    if risk and risk != "All Risk":
        stmt = stmt.where(AccessLog.risk_level == risk)
    if decision and decision != "All Decisions":
        stmt = stmt.where(AccessLog.decision == decision)
    
    stmt = stmt.limit(limit)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/export")
async def export_logs_csv(db: AsyncSession = Depends(get_db)):
    """Exports access audit trail as a downloadable CSV file."""
    stmt = select(AccessLog).order_by(desc(AccessLog.timestamp)).limit(1000)
    res = await db.execute(stmt)
    logs = res.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Person ID", "Full Name", "User Type", "Gate", "Risk Level", "Decision", "Method", "Reason"])
    
    for l in logs:
        writer.writerow([
            l.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            l.person_id,
            l.full_name,
            l.user_type,
            l.gate_id,
            l.risk_level,
            l.decision,
            l.method,
            l.reason or ""
        ])

    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=vignan-access-logs.csv"}
    )
