import time
import datetime
from typing import Dict, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException

from backend.config import settings
from backend.models import User, Gate, AccessLog, Alert
from backend.schemas import ScanRequest, ScanResponse
from backend.services.websocket_manager import ws_manager

class IngestionService:
    def __init__(self):
        # In-memory anti-rebound tracking: (gate_id, credential_id) -> last_tap_time
        self._tap_history: Dict[Tuple[str, str], float] = {}

    def check_anti_rebound(self, gate_id: str, credential_id: str) -> None:
        """Enforces anti-rebound rate limiting (blocks duplicate taps within 1.5 seconds)."""
        key = (gate_id, credential_id.upper())
        now = time.time()
        last_tap = self._tap_history.get(key, 0)

        if now - last_tap < settings.ANTI_REBOUND_SECONDS:
            raise HTTPException(
                status_code=429,
                detail=f"Anti-rebound reject: Duplicate tap on gate '{gate_id}' within {settings.ANTI_REBOUND_SECONDS}s window."
            )
        self._tap_history[key] = now

    async def process_scan(self, req: ScanRequest, db: AsyncSession) -> ScanResponse:
        cred = req.credential_id.strip()
        self.check_anti_rebound(req.gate_id, cred)

        # Query user by person_id or rfid_uid
        stmt = select(User).where((User.person_id == cred) | (User.rfid_uid == cred.upper()))
        result = await db.execute(stmt)
        user = result.scalars().first()

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_str = now_dt.strftime("%H:%M:%S")

        if user and user.status == "ACTIVE":
            decision = "GRANTED"
            risk_level = "LOW"
            barrier_command = "OPEN_BARRIER"
            reason = f"Verified {user.role}: {user.full_name} ({user.department or 'General'})"
            person_id = user.person_id
            full_name = user.full_name
            user_type = user.role

            # Increment Gate entries counter
            gate_stmt = select(Gate).where(Gate.gate_name == req.gate_id)
            gate_res = await db.execute(gate_stmt)
            gate_obj = gate_res.scalars().first()
            if gate_obj:
                gate_obj.today_entries += 1
                await db.commit()

        elif user and user.status != "ACTIVE":
            decision = "DENIED"
            risk_level = "HIGH"
            barrier_command = "LOCK_BARRIER"
            reason = f"Suspended credential: {user.full_name} ({user.status})"
            person_id = user.person_id
            full_name = user.full_name
            user_type = user.role

            # Generate security alert
            alert = Alert(
                severity="HIGH",
                gate_id=req.gate_id,
                user_identifier=f"{person_id} ({full_name})",
                reason=reason,
                action_required="Officer manual inspection required",
                status="ACTIVE"
            )
            db.add(alert)
            await db.commit()

            await ws_manager.broadcast("NEW_ALERT", {
                "severity": "HIGH",
                "gate": req.gate_id,
                "reason": reason
            })

        else:
            decision = "DENIED"
            risk_level = "HIGH"
            barrier_command = "LOCK_BARRIER"
            reason = "Unregistered credential UID / Unknown visitor"
            person_id = cred
            full_name = "Unknown Subject"
            user_type = req.user_type or "Visitor"

            # Generate security alert
            alert = Alert(
                severity="HIGH",
                gate_id=req.gate_id,
                user_identifier=f"Unregistered ID: {cred}",
                reason=reason,
                action_required="Security guard verification required",
                status="ACTIVE"
            )
            db.add(alert)
            await db.commit()

            await ws_manager.broadcast("NEW_ALERT", {
                "severity": "HIGH",
                "gate": req.gate_id,
                "reason": reason
            })

        # Record Access Log
        log = AccessLog(
            timestamp=now_dt,
            person_id=person_id,
            full_name=full_name,
            user_type=user_type,
            gate_id=req.gate_id,
            risk_level=risk_level,
            decision=decision,
            method=req.method,
            reason=reason
        )
        db.add(log)
        await db.commit()

        # Broadcast live scan event to all SOC Dashboards
        await ws_manager.broadcast("SCAN_EVENT", {
            "timestamp": now_str,
            "person_id": person_id,
            "full_name": full_name,
            "user_type": user_type,
            "gate": req.gate_id,
            "risk": risk_level,
            "decision": decision,
            "method": req.method
        })

        return ScanResponse(
            decision=decision,
            person_id=person_id,
            full_name=full_name,
            user_type=user_type,
            gate_id=req.gate_id,
            risk_level=risk_level,
            barrier_command=barrier_command,
            reason=reason,
            timestamp=now_str
        )

ingestion_service = IngestionService()
