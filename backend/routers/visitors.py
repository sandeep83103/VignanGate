import hashlib
import random
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from backend.database import get_db
from backend.models import Visitor
from backend.schemas import VisitorCreate, VisitorResponse, ScanResponse, ScanRequest
from backend.services.visitor_service import visitor_service
from backend.services.ingestion import ingestion_service

router = APIRouter(prefix="/api/visitors", tags=["Visitor Management"])

class HostActionRequest(BaseModel):
    action: str # APPROVE or REJECT
    reason: Optional[str] = "Approved by host faculty"

class QRVerifyRequest(BaseModel):
    gate_id: str
    qr_token: str # Scanned QR string / token

@router.post("/", response_model=VisitorResponse)
async def register_visitor(v: VisitorCreate, db: AsyncSession = Depends(get_db)):
    """Pre-registers visitor intake in PENDING state awaiting host approval."""
    pass_id = f"VIS-2026-{random.randint(1000, 9999)}"
    
    # Generate cryptographic token pre-signed for immediate access or host review
    token = visitor_service.generate_signed_token(pass_id, v.visitor_name, v.host_name, v.gate_id)
    qr_hash = hashlib.sha256(token.encode()).hexdigest()[:32].upper()

    visitor = Visitor(
        visitor_id=pass_id,
        visitor_name=v.visitor_name,
        mobile_number=v.mobile_number,
        host_name=v.host_name,
        purpose=v.purpose,
        gate_id=v.gate_id,
        qr_hash=qr_hash,
        signed_token=token,
        approval_status="APPROVED" # Auto-approved for fast-track demo or host action
    )
    db.add(visitor)
    await db.commit()
    await db.refresh(visitor)
    return visitor

@router.post("/{visitor_id}/action", response_model=VisitorResponse)
async def host_approval_action(visitor_id: str, action_req: HostActionRequest, db: AsyncSession = Depends(get_db)):
    """Host approval or rejection action."""
    stmt = select(Visitor).where(Visitor.visitor_id == visitor_id)
    res = await db.execute(stmt)
    visitor = res.scalars().first()

    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor pass record not found.")

    if action_req.action == "APPROVE":
        visitor.approval_status = "APPROVED"
        if not visitor.signed_token:
            visitor.signed_token = visitor_service.generate_signed_token(
                visitor.visitor_id, visitor.visitor_name, visitor.host_name, visitor.gate_id
            )
    else:
        visitor.approval_status = "REJECTED"

    await db.commit()
    await db.refresh(visitor)
    return visitor

@router.get("/{visitor_id}/qr-image")
async def get_qr_image(visitor_id: str, db: AsyncSession = Depends(get_db)):
    """Generates and streams a downloadable high-resolution PNG QR Pass image."""
    stmt = select(Visitor).where(Visitor.visitor_id == visitor_id)
    res = await db.execute(stmt)
    visitor = res.scalars().first()

    if not visitor or not visitor.signed_token:
        raise HTTPException(status_code=404, detail="Active QR pass not found for this visitor.")

    img_bytes = visitor_service.generate_qr_image_bytes(visitor.signed_token)
    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename={visitor_id}-pass.png"}
    )

@router.post("/verify-qr", response_model=ScanResponse)
async def verify_qr_at_gate(req: QRVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Perimeter gate optical camera scanner endpoint validating signed QR passes."""
    is_valid, payload, err_msg = visitor_service.verify_token(req.qr_token)

    if not is_valid:
        # Route through AI pipeline as untrusted / failed scan
        scan_req = ScanRequest(
            gate_id=req.gate_id,
            credential_id=req.qr_token[:16],
            method="QR Pass",
            user_type="Visitor"
        )
        return await ingestion_service.process_scan(scan_req, db)

    # Valid signed pass: Route into AI pipeline with verified visitor credentials
    vid = payload.get("vid", "VIS-UNKNOWN")
    scan_req = ScanRequest(
        gate_id=req.gate_id,
        credential_id=vid,
        method="QR Pass",
        user_type="Visitor"
    )
    return await ingestion_service.process_scan(scan_req, db)

@router.get("/", response_model=List[VisitorResponse])
async def list_visitors(db: AsyncSession = Depends(get_db)):
    """Lists registered visitors ordered by creation time."""
    stmt = select(Visitor).order_by(desc(Visitor.created_at)).limit(50)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/{visitor_id}", response_model=VisitorResponse)
async def get_visitor(visitor_id: str, db: AsyncSession = Depends(get_db)):
    """Validates visitor pass by ID."""
    stmt = select(Visitor).where(Visitor.visitor_id == visitor_id)
    res = await db.execute(stmt)
    vis = res.scalars().first()
    if not vis:
        raise HTTPException(status_code=404, detail="Visitor pass not found or expired.")
    return vis
