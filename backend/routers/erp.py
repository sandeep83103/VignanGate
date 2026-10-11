from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from backend.database import get_db
from backend.services.erp_sync import erp_sync_service
from backend.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/erp", tags=["Institutional ERP & SIS Sync"])

class BulkImportItem(BaseModel):
    person_id: str
    full_name: str
    role: str
    department: Optional[str] = "General"
    rfid_uid: Optional[str] = None
    status: Optional[str] = "ACTIVE"

@router.post("/sync")
async def trigger_erp_sync(db: AsyncSession = Depends(get_db)):
    """Triggers institutional delta synchronization with Vignan University SIS database."""
    log = await erp_sync_service.execute_delta_sync(db)

    # Broadcast ERP sync completed to connected SOC dashboards
    await ws_manager.broadcast("ERP_SYNC_COMPLETED", {
        "sync_id": log.sync_id,
        "added": log.records_added,
        "updated": log.records_updated,
        "suspended": log.records_suspended,
        "duration_ms": log.duration_ms
    })

    return {
        "status": "SYNC_SUCCESSFUL",
        "sync_id": log.sync_id,
        "source": log.source,
        "records_processed": log.records_processed,
        "records_added": log.records_added,
        "records_updated": log.records_updated,
        "records_suspended": log.records_suspended,
        "duration_ms": log.duration_ms
    }

@router.get("/status")
async def get_erp_status(db: AsyncSession = Depends(get_db)):
    """Retrieves current credential counts and last synchronization telemetry."""
    return await erp_sync_service.get_sync_status(db)

@router.post("/bulk-import")
async def bulk_import_credentials(items: List[BulkImportItem], db: AsyncSession = Depends(get_db)):
    """Allows institutional bulk upload of student & faculty credentials."""
    records = [item.model_dump() for item in items]
    log = await erp_sync_service.execute_delta_sync(db, delta_records=records)
    return {
        "status": "BULK_IMPORT_COMPLETED",
        "total_imported": len(items),
        "sync_id": log.sync_id,
        "duration_ms": log.duration_ms
    }
