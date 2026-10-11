import time
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import logging

from backend.models import User, ERPSyncLog

logger = logging.getLogger("vignan.erp_sync")

# Pre-configured institutional delta batch simulating Vignan University SIS updates
MOCK_SIS_DELTA_BATCH = [
    {
        "person_id": "STU20261401",
        "full_name": "V. Sai Krishna",
        "role": "Student",
        "department": "CSE (AI & ML)",
        "rfid_uid": "F188AA01",
        "status": "ACTIVE"
    },
    {
        "person_id": "STU20261402",
        "full_name": "G. Bhavani",
        "role": "Student",
        "department": "ECE",
        "rfid_uid": "F188AA02",
        "status": "ACTIVE"
    },
    {
        "person_id": "FAC10550",
        "full_name": "Dr. K. N. Murthy",
        "role": "Faculty",
        "department": "Information Technology",
        "rfid_uid": "E422BC99",
        "status": "ACTIVE"
    },
    {
        "person_id": "STU20261199", # Existing student graduating / revoking access
        "full_name": "K. Teja",
        "role": "Student",
        "department": "Mechanical",
        "rfid_uid": "E912FA00",
        "status": "SUSPENDED"
    }
]

class ERPSyncService:
    """
    Connects to Vignan University Central Student Information System (SIS) / ERP.
    Executes automated delta syncs for student admissions, faculty appointments,
    and disciplinary suspensions.
    """

    async def execute_delta_sync(self, db: AsyncSession, delta_records: Optional[List[Dict[str, Any]]] = None) -> ERPSyncLog:
        start_time = time.perf_counter()
        records = delta_records if delta_records is not None else MOCK_SIS_DELTA_BATCH

        added = 0
        updated = 0
        suspended = 0

        for item in records:
            pid = item["person_id"]
            stmt = select(User).where(User.person_id == pid)
            res = await db.execute(stmt)
            existing_user = res.scalars().first()

            if existing_user:
                # Update existing user attributes
                existing_user.full_name = item.get("full_name", existing_user.full_name)
                existing_user.role = item.get("role", existing_user.role)
                existing_user.department = item.get("department", existing_user.department)
                existing_user.rfid_uid = item.get("rfid_uid", existing_user.rfid_uid)
                new_status = item.get("status", existing_user.status)
                
                if new_status == "SUSPENDED" and existing_user.status != "SUSPENDED":
                    suspended += 1
                else:
                    updated += 1

                existing_user.status = new_status
            else:
                # Insert newly enrolled student or faculty
                new_user = User(
                    person_id=item["person_id"],
                    full_name=item["full_name"],
                    role=item["role"],
                    department=item.get("department", "General"),
                    rfid_uid=item.get("rfid_uid"),
                    status=item.get("status", "ACTIVE")
                )
                db.add(new_user)
                added += 1

        await db.commit()

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Log Sync Audit
        sync_log = ERPSyncLog(
            source="Vignan-SIS-Cloud",
            records_processed=len(records),
            records_added=added,
            records_updated=updated,
            records_suspended=suspended,
            status="COMPLETED",
            duration_ms=duration_ms
        )
        db.add(sync_log)
        await db.commit()
        await db.refresh(sync_log)

        logger.info(
            f"[ERP Sync] Completed in {duration_ms}ms. "
            f"Added: {added}, Updated: {updated}, Suspended: {suspended}"
        )
        return sync_log

    async def get_sync_status(self, db: AsyncSession) -> Dict[str, Any]:
        """Returns statistics on institutional records and last synchronization."""
        total_users_stmt = select(User)
        res = await db.execute(total_users_stmt)
        users = res.scalars().all()

        last_sync_stmt = select(ERPSyncLog).order_by(ERPSyncLog.timestamp.desc()).limit(1)
        res_sync = await db.execute(last_sync_stmt)
        last_log = res_sync.scalars().first()

        active_count = sum(1 for u in users if u.status == "ACTIVE")
        suspended_count = sum(1 for u in users if u.status == "SUSPENDED")

        return {
            "total_credentials": len(users),
            "active_credentials": active_count,
            "suspended_credentials": suspended_count,
            "last_sync_time": last_log.timestamp.isoformat() if last_log else None,
            "last_sync_status": last_log.status if last_log else "NO_SYNC_YET",
            "last_sync_duration_ms": last_log.duration_ms if last_log else 0
        }

erp_sync_service = ERPSyncService()
