import hashlib
import datetime
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from backend.database import get_db
from backend.models import Visitor
from backend.schemas import VisitorCreate, VisitorResponse

router = APIRouter(prefix="/api/visitors", tags=["Visitor Management"])

@router.post("/", response_model=VisitorResponse)
async def register_visitor(v: VisitorCreate, db: AsyncSession = Depends(get_db)):
    """Registers visitor, computes cryptographic QR hash, and stores record."""
    pass_id = f"VIS-2026-{random.randint(1000, 9999)}"
    
    # Compute signature hash for QR verification
    raw_hash = f"{pass_id}:{v.visitor_name}:{v.gate_id}:{datetime.datetime.now(datetime.timezone.utc).isoformat()}"
    qr_hash = hashlib.sha256(raw_hash.encode()).hexdigest()[:32].upper()

    visitor = Visitor(
        visitor_id=pass_id,
        visitor_name=v.visitor_name,
        mobile_number=v.mobile_number,
        host_name=v.host_name,
        purpose=v.purpose,
        gate_id=v.gate_id,
        qr_hash=qr_hash,
        approval_status="APPROVED"
    )
    db.add(visitor)
    await db.commit()
    await db.refresh(visitor)
    return visitor

@router.get("/", response_model=List[VisitorResponse])
async def list_visitors(db: AsyncSession = Depends(get_db)):
    """Lists registered visitors ordered by registration time."""
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
