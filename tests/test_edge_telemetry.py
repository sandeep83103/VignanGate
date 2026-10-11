"""
==============================================================================
Unit & Integration Tests for Phase 2: Edge Hardware & Telemetry
==============================================================================
"""

import pytest
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.edge_simulator import ESP32GateController, OfflineCacheSimulator


def test_offline_cache_whitelist_lookup():
    cache = OfflineCacheSimulator()
    # Test valid faculty
    fac = cache.check_whitelist("C48A109E")
    assert fac is not None
    assert fac["name"] == "Dr. Priya Rao"
    assert fac["role"] == "Faculty"
    assert fac["auth"] is True

    # Test case insensitivity
    stu = cache.check_whitelist("a35f821b")
    assert stu is not None
    assert stu["pid"] == "STU20261245"

    # Test unknown card
    unknown = cache.check_whitelist("0000FFFF")
    assert unknown is None


def test_heartbeat_payload_structure():
    gate = ESP32GateController("UG-01", "University Gate (Main)")
    hb = gate.generate_heartbeat()

    required_keys = [
        "device_id", "gate", "status", "signal_percent",
        "barrier_state", "tailgating_flag", "cached_whitelist",
        "free_heap", "uptime_sec", "timestamp"
    ]
    for key in required_keys:
        assert key in hb, f"Missing key: {key} in heartbeat"

    assert hb["status"] == "ONLINE"
    assert hb["barrier_state"] == "CLOSED"
    assert hb["uptime_sec"] == 5
    assert hb["cached_whitelist"] >= 5


def test_online_rfid_tap_emission():
    gate = ESP32GateController("LG-01", "Lara Gate")
    res = gate.simulate_rfid_tap("A35F821B")

    assert res["mode"] == "ONLINE_MQTT"
    assert res["gate_id"] == "LG-01"
    assert res["card_uid"] == "A35F821B"
    assert res["method"] == "RFID"


def test_offline_fallback_and_event_queueing():
    gate = ESP32GateController("LIB-01", "Library Gate")
    gate.is_online = False

    # Valid Card Tap during network failure
    res_valid = gate.simulate_rfid_tap("A35F821B")
    assert res_valid["mode"] == "OFFLINE_LITTLEFS"
    assert res_valid["decision"] == "GRANTED"
    assert res_valid["matched_user"] == "Rahul Kumar"
    assert gate.barrier_open is True

    # Invalid Card Tap during network failure
    res_invalid = gate.simulate_rfid_tap("BAD_CARD_123")
    assert res_invalid["mode"] == "OFFLINE_LITTLEFS"
    assert res_invalid["decision"] == "DENIED"

    # Verify offline flash queue has recorded both attempts
    assert len(gate.cache.offline_queue) == 2
    assert gate.cache.offline_queue[0]["decision"] == "GRANTED_OFFLINE"
    assert gate.cache.offline_queue[1]["decision"] == "DENIED_OFFLINE"

    # Simulate network restoration & queue flush
    gate.is_online = True
    flushed_records = gate.cache.flush_queue()
    assert len(flushed_records) == 2
    assert len(gate.cache.offline_queue) == 0
