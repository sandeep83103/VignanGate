from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Telemetry Schemas
class TelemetryPayload(BaseModel):
    device_id: str
    gate: str
    status: str
    signal_percent: int = Field(ge=0, le=100)
    barrier_state: str = "CLOSED"
    tailgating_flag: bool = False
    cached_whitelist: Optional[int] = 0
    free_heap: Optional[int] = 0
    uptime_sec: Optional[int] = 0
    timestamp: Optional[int] = None

# Scan Ingestion Request
class ScanRequest(BaseModel):
    gate_id: str
    credential_id: str # RFID UID or Person ID (e.g. STU20261245 or A35F821B)
    method: str = "RFID" # RFID, QR Pass, Manual
    user_type: Optional[str] = "Student"

# Scan Evaluation Response
class ScanResponse(BaseModel):
    decision: str # GRANTED, DENIED, MANUAL REVIEW
    person_id: str
    full_name: str
    user_type: str
    gate_id: str
    risk_level: str
    barrier_command: str # OPEN_BARRIER, LOCK_BARRIER
    reason: str
    timestamp: str

# Barrier Remote Command
class BarrierCommand(BaseModel):
    gate_id: str
    action: str # OPEN_BARRIER, LOCK_BARRIER
    officer_id: Optional[str] = "SOC-AUTO"

# Visitor Registration
class VisitorCreate(BaseModel):
    visitor_name: str
    mobile_number: str
    host_name: str
    purpose: str
    gate_id: str

class VisitorResponse(BaseModel):
    visitor_id: str
    visitor_name: str
    mobile_number: str
    host_name: str
    purpose: str
    gate_id: str
    approval_status: str
    qr_hash: str
    created_at: datetime

# Alert Schemas
class AlertUpdate(BaseModel):
    status: Optional[str] = None # ACTIVE, RESOLVED
    assigned_officer: Optional[str] = None

class AlertResponse(BaseModel):
    alert_id: int
    timestamp: datetime
    severity: str
    gate_id: str
    user_identifier: str
    reason: str
    action_required: str
    status: str
    assigned_officer: str

# Access Log Response
class AccessLogResponse(BaseModel):
    log_id: int
    timestamp: datetime
    person_id: str
    full_name: str
    user_type: str
    gate_id: str
    risk_level: str
    decision: str
    method: str
    reason: Optional[str]
