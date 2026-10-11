"""
==============================================================================
VIGNAN SMART ACCESS — ESP32 HARDWARE EMULATOR & TEST BENCH
Simulates physical ESP32 gate microcontrollers, RC522 RFID scanners,
beam-break sensors, and LittleFS offline caching over MQTT / Local Mock.
==============================================================================
"""

import json
import time
import random
from typing import Dict, Any, Optional

class OfflineCacheSimulator:
    """Emulates LittleFS flash memory storage and fast in-memory RAM lookup."""
    
    def __init__(self):
        self.whitelist: Dict[str, Dict[str, Any]] = {
            "A35F821B": {"pid": "STU20261245", "name": "Rahul Kumar", "role": "Student", "auth": True},
            "C48A109E": {"pid": "FAC10421", "name": "Dr. Priya Rao", "role": "Faculty", "auth": True},
            "D291FB33": {"pid": "STU20261082", "name": "Ananya Reddy", "role": "Student", "auth": True},
            "FF12E844": {"pid": "SEC001", "name": "Chief Security Officer", "role": "Security", "auth": True},
            "EE77CA12": {"pid": "EMERG001", "name": "Campus Medical Emergency", "role": "Emergency", "auth": True}
        }
        self.offline_queue = []

    def check_whitelist(self, uid: str) -> Optional[Dict[str, Any]]:
        return self.whitelist.get(uid.upper())

    def record_offline_event(self, uid: str, decision: str) -> None:
        self.offline_queue.append({
            "uid": uid,
            "decision": decision,
            "timestamp": int(time.time()),
            "mode": "OFFLINE_LITTLEFS"
        })

    def flush_queue(self) -> list:
        events = list(self.offline_queue)
        self.offline_queue.clear()
        return events


class ESP32GateController:
    """Emulates the firmware behavior of an ESP32 gate controller."""

    def __init__(self, gate_id: str, gate_name: str):
        self.gate_id = gate_id
        self.gate_name = gate_name
        self.is_online = True
        self.barrier_open = False
        self.cache = OfflineCacheSimulator()
        self.uptime_sec = 0

    def generate_heartbeat(self) -> Dict[str, Any]:
        """Generates MQTT telemetry heartbeat JSON matching firmware schema."""
        self.uptime_sec += 5
        return {
            "device_id": f"ESP32-{self.gate_id}",
            "gate": self.gate_name,
            "status": "ONLINE" if self.is_online else "OFFLINE",
            "signal_percent": random.randint(84, 98),
            "barrier_state": "OPEN" if self.barrier_open else "CLOSED",
            "tailgating_flag": False,
            "cached_whitelist": len(self.cache.whitelist),
            "free_heap": random.randint(184000, 210000),
            "uptime_sec": self.uptime_sec,
            "timestamp": int(time.time())
        }

    def simulate_rfid_tap(self, uid: str) -> Dict[str, Any]:
        """Handles RFID card tap according to online/offline state machine."""
        uid_clean = uid.strip().upper()
        
        if self.is_online:
            # Pushes scan event payload to cloud
            return {
                "mode": "ONLINE_MQTT",
                "gate_id": self.gate_id,
                "card_uid": uid_clean,
                "method": "RFID",
                "device_timestamp": int(time.time()),
                "rssi": -55
            }
        else:
            # Offline LittleFS evaluation
            match = self.cache.check_whitelist(uid_clean)
            if match and match["auth"]:
                self.barrier_open = True
                self.cache.record_offline_event(uid_clean, "GRANTED_OFFLINE")
                return {
                    "mode": "OFFLINE_LITTLEFS",
                    "decision": "GRANTED",
                    "matched_user": match["name"],
                    "role": match["role"],
                    "barrier_actuation": "OPEN_3500MS"
                }
            else:
                self.cache.record_offline_event(uid_clean, "DENIED_OFFLINE")
                return {
                    "mode": "OFFLINE_LITTLEFS",
                    "decision": "DENIED",
                    "reason": "Unregistered Offline UID",
                    "barrier_actuation": "HOLD_CLOSED"
                }


def main():
    print("==================================================================")
    print("  VIGNAN SMART ACCESS — ESP32 HARDWARE SIMULATOR (PHASE 2)        ")
    print("==================================================================")
    
    ug_gate = ESP32GateController("UG-01", "University Gate (Main)")
    print(f"Initialized virtual controller: {ug_gate.gate_name}")
    print("Generating sample telemetry heartbeat:")
    print(json.dumps(ug_gate.generate_heartbeat(), indent=2))

    print("\n--- Testing Online RFID Tap (STU20261245 / A35F821B) ---")
    online_res = ug_gate.simulate_rfid_tap("A35F821B")
    print(json.dumps(online_res, indent=2))

    print("\n--- Simulating Network Disconnect (Offline Mode) ---")
    ug_gate.is_online = False
    offline_valid = ug_gate.simulate_rfid_tap("A35F821B")
    print("Valid Tap in Offline Mode:")
    print(json.dumps(offline_valid, indent=2))

    offline_invalid = ug_gate.simulate_rfid_tap("9999DEAD")
    print("\nInvalid Tap in Offline Mode:")
    print(json.dumps(offline_invalid, indent=2))

    print(f"\nQueued Offline Events in Flash: {len(ug_gate.cache.offline_queue)}")
    ug_gate.is_online = True
    flushed = ug_gate.cache.flush_queue()
    print(f"Flushed upon Network Reconnection: {len(flushed)} records.")


if __name__ == "__main__":
    main()
