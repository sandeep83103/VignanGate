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
    emergency_evacuation: Optional[bool] = False
    cached_whitelist: Optional[int] = 0
    free_heap: Optional[int] = 0
    uptime_sec: Optional[int] = 0
    timestamp: Optional[int] = None

# Emergency Evacuation Schemas
class EmergencyReleaseRequest(BaseModel):
    triggered_by: Optional[str] = "Fire Alarm Control Panel (FACP-Main)"
    reason: Optional[str] = "Central Fire Alarm Interlock Tripped (GPIO 35)"

class EmergencyResetRequest(BaseModel):
    officer_id: Optional[str] = "CHIEF_SECURITY"
    notes: Optional[str] = "All zones cleared. Normal perimeter operations restored."

class EmergencyStatusResponse(BaseModel):
    status: str
    timestamp: str
    active: bool
    gates_affected: List[str]
    message: str

# Scan Ingestion Request
class ScanRequest(BaseModel):
    gate_id: str
    credential_id: str # RFID UID or Person ID (e.g. STU20261245 or A35F821B)
    method: str = "RFID" # RFID, QR Pass, Manual
    user_type: Optional[str] = "Student"

class AgentTraceItem(BaseModel):
    agent_name: str
    status: str
    duration_ms: float
    output_summary: str

# Scan Evaluation Response
class ScanResponse(BaseModel):
    decision: str # GRANTED, DENIED, MANUAL REVIEW
    person_id: str
    full_name: str
    user_type: str
    gate_id: str
    risk_level: str
    risk_score: float = 0.0
    barrier_command: str # OPEN_BARRIER, LOCK_BARRIER, HOLD_CLOSED
    reason: str
    timestamp: str
    method: str = "RFID"
    anomaly_flags: List[str] = []
    agent_trace: List[AgentTraceItem] = []
    pipeline_latency_ms: float = 0.0

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
