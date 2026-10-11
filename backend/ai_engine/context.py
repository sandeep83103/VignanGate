from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from backend.models import User

@dataclass
class AgentTraceStep:
    agent_name: str
    status: str # COMPLETED, FAILED, SKIPPED
    duration_ms: float
    output_summary: str
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AccessContext:
    # Ingestion Input
    gate_id: str
    credential_id: str
    method: str = "RFID"
    user_type: Optional[str] = "Student"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Agent 1: Identity Evaluation
    user: Optional[User] = None
    identity_status: str = "PENDING" # VERIFIED, UNREGISTERED, SUSPENDED, MALFORMED
    person_id: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None

    # Agent 2: Authorization Evaluation
    auth_status: str = "PENDING" # AUTHORIZED, CURFEW_RESTRICTED, ZONE_RESTRICTED, UNAUTHORIZED
    auth_reason: str = ""

    # Agent 3: Risk Evaluation
    risk_score: float = 0.0 # 0.0 to 100.0
    risk_level: str = "LOW" # LOW, MEDIUM, HIGH
    risk_factors: List[str] = field(default_factory=list)

    # Agent 4: Anomaly Evaluation
    anomaly_flags: List[str] = field(default_factory=list) # ANTI_PASSBACK, IMPOSSIBLE_VELOCITY, RAPID_SCAN
    has_anomaly: bool = False

    # Agent 5: Policy Output
    policy_decision: str = "PENDING" # FAST_LANE_GRANT, STANDARD_INSPECT, MANUAL_REVIEW_DENY
    barrier_command: str = "HOLD_CLOSED" # OPEN_BARRIER, LOCK_BARRIER, HOLD_CLOSED
    final_reason: str = ""

    # Agent 6: Notification Output
    notification_dispatched: bool = False
    alert_id: Optional[int] = None

    # Pipeline Performance & Observability
    execution_trace: List[AgentTraceStep] = field(default_factory=list)
    total_pipeline_ms: float = 0.0
