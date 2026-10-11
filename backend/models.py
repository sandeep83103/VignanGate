import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from backend.database import Base

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)

class User(Base):
    __tablename__ = "users"

    person_id = Column(String(32), primary_key=True, index=True) # STU20261245, FAC10421
    full_name = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False) # Student, Faculty, Staff, Visitor, Vendor
    department = Column(String(64), nullable=True) # CSE, ECE, Administration
    rfid_uid = Column(String(32), unique=True, index=True, nullable=True) # e.g. A35F821B
    status = Column(String(16), default="ACTIVE") # ACTIVE, SUSPENDED, EXPIRED


class Gate(Base):
    __tablename__ = "gates"

    gate_id = Column(String(32), primary_key=True) # GATE-UG-01, GATE-LG-01, GATE-LIB-01
    gate_name = Column(String(64), unique=True, nullable=False) # University Gate, Lara Gate, Library Gate
    location_code = Column(String(32), nullable=False)
    status = Column(String(16), default="ONLINE") # ONLINE, OFFLINE, MAINTENANCE
    barrier_state = Column(String(16), default="CLOSED") # CLOSED, OPEN, LOCKED
    today_entries = Column(Integer, default=0)
    current_risk = Column(String(16), default="LOW") # LOW, MEDIUM, HIGH


class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String(32), primary_key=True) # ESP32-UG-001, RFID-UG-001
    gate_id = Column(String(32), ForeignKey("gates.gate_id"), nullable=False)
    device_type = Column(String(32), nullable=False) # ESP32 Controller, RFID Reader, Camera, Barrier
    status = Column(String(16), default="ONLINE") # ONLINE, OFFLINE
    signal_percent = Column(Integer, default=90)
    last_heartbeat = Column(DateTime, default=utc_now)


class Visitor(Base):
    __tablename__ = "visitors"

    visitor_id = Column(String(32), primary_key=True, index=True) # VIS-2026-9812
    visitor_name = Column(String(128), nullable=False)
    mobile_number = Column(String(16), nullable=False)
    host_name = Column(String(128), nullable=False)
    purpose = Column(String(256), nullable=False)
    gate_id = Column(String(32), nullable=False)
    qr_hash = Column(String(128), nullable=True)
    signed_token = Column(Text, nullable=True)
    approval_status = Column(String(16), default="PENDING") # PENDING, APPROVED, REJECTED
    created_at = Column(DateTime, default=utc_now)


class AccessLog(Base):
    __tablename__ = "access_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
    person_id = Column(String(32), nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    user_type = Column(String(32), nullable=False)
    gate_id = Column(String(32), nullable=False, index=True)
    risk_level = Column(String(16), default="LOW") # LOW, MEDIUM, HIGH
    decision = Column(String(16), default="GRANTED") # GRANTED, DENIED, MANUAL REVIEW
    method = Column(String(16), default="RFID") # RFID, QR Pass, Manual
    reason = Column(String(256), nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
    severity = Column(String(16), nullable=False) # HIGH, MEDIUM, LOW
    gate_id = Column(String(32), nullable=False)
    user_identifier = Column(String(64), nullable=False)
    reason = Column(String(256), nullable=False)
    action_required = Column(String(256), nullable=False)
    status = Column(String(16), default="ACTIVE") # ACTIVE, RESOLVED
    assigned_officer = Column(String(64), default="Unassigned")


class ERPSyncLog(Base):
    __tablename__ = "erp_sync_logs"

    sync_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
    source = Column(String(64), default="Vignan-SIS-Cloud")
    records_processed = Column(Integer, default=0)
    records_added = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_suspended = Column(Integer, default=0)
    status = Column(String(16), default="COMPLETED") # COMPLETED, FAILED
    duration_ms = Column(Integer, default=0)

