# Vignan Smart Access — Field Deployment & Commissioning Checklist (Phase 6)

**Institution:** Vignan's Foundation for Science, Technology & Research (VFSTR), Vadlamudi  
**Document ID:** `VFSTR-SA-ENG-2026-CHKLST-P6`  
**Security Level:** Internal Engineering / Facility Management  
**Applicable Gates:**
- **Gate 3 (Pilot):** Library Gate (`GATE-LIB-01`)
- **Gate 2 (Secondary):** Lara Gate (`GATE-LG-01`)
- **Gate 1 (Main Perimeter):** University Gate (`GATE-UG-01`)

---

## 1. Physical & Civil Infrastructure Verification

- [ ] **1.1 Foundation & Mounting:** Verify concrete plinth level and anchor bolt torque (Grade 8.8 M12 anchors torqued to 45 Nm).
- [ ] **1.2 Weather Enclosure Integrity:** Confirm IP65 weather seals on the ESP32 enclosure and cable gland conduits.
- [ ] **1.3 Power Supply & UPS Backing:**
  - [ ] Primary 230V AC mains line measured between 215V–240V AC.
  - [ ] Mean Well 12V 5A industrial DIN-rail power supply providing stable 12.1V DC output.
  - [ ] In-line 12V 7Ah sealed lead-acid (SLA) battery backup providing $\ge 4\text{ hours}$ autonomous runtime upon campus grid blackout.
- [ ] **1.4 Grounding & Surge Protection:** Earth ground resistance measured at $< 2.0\text{ }\Omega$ at earth pit electrode.

---

## 2. Low-Voltage Sensor & Actuator Cabling

- [ ] **2.1 RC522 RFID SPI Wiring:** Shielded twisted pair (STP) cable used for SPI bus (`SCK`, `MISO`, `MOSI`, `SS`) with total length $< 1.5\text{ m}$ to prevent bus capacitance degradation.
- [ ] **2.2 Optical QR Camera:** High-speed shielded USB/UART interface properly grounded with zero signal distortion.
- [ ] **2.3 Anti-Tailgating Sensors:**
  - [ ] Dual infrared photocell array beam aligned with green indicator LED illuminated.
  - [ ] Beam break test triggers interrupt state change on ESP32 `BEAM_SENSOR_PIN` (GPIO 34) within $< 10\text{ ms}$.
- [ ] **2.4 Boom Barrier Relay Connection:**
  - [ ] Relay dry contacts wired to barrier motor control board input.
  - [ ] Test command pulse of $3500\text{ ms}$ triggers full 90-degree opening without mechanical shudder.

---

## 3. Physical Fire Alarm Interlock (GPIO 35) Commissioning

> [!CRITICAL]
> Under national building safety standards (NBC 2016 Part 4), all automated access barriers must fail-open immediately during fire alarm activation.

- [ ] **3.1 Hardwired FACP Connection:** Dry-contact relay from campus Central Fire Alarm Control Panel (FACP) connected to ESP32 `FIRE_ALARM_PIN` (GPIO 35) and Common Ground (`GND`).
- [ ] **3.2 Active-LOW Interrupt Test:**
  - [ ] In normal state, GPIO 35 voltage measured at $3.3\text{V}$ (Internal Pull-Up engaged).
  - [ ] When test key turned on FACP, dry-contact closes to ground ($0.0\text{V}$).
  - [ ] ESP32 hardware interrupt fires immediately:
    - [ ] Barrier relay energizes continuously into OPEN position.
    - [ ] Dual status LEDs flash in strobe evacuation pattern.
    - [ ] Auto-closing timer is completely bypassed and disengaged.
    - [ ] Telemetry heartbeat immediately transmits `"emergency_evacuation": true`.
- [ ] **3.3 Reset Validation:** When FACP is reset, barrier returns to secure closed state upon authoritative SOC confirmation command.

---

## 4. Network Commissioning & MQTT Connectivity

- [ ] **4.1 Dedicated IoT VLAN:** Connect to campus Wi-Fi network `VIGNAN_CAMPUS_IOT` mapped to VLAN 40 (isolated from student guest network).
- [ ] **4.2 Signal Quality:** Wi-Fi RSSI measured $\ge -65\text{ dBm}$ (Telemetry signal percentage $\ge 85\%$).
- [ ] **4.3 MQTT Broker Handshake:** ESP32 successfully handshakes with `mqtt.vignan.internal:1883` within $< 800\text{ ms}$.
- [ ] **4.4 WebSocket Broadcast:** SOC web console (`/ws/soc`) receives live telemetry frame within $< 50\text{ ms}$ of publish.

---

## 5. Offline Cache (`LittleFS`) Resilience Drill

- [ ] **5.1 Cache Synchronization:** Flash memory contains up-to-date active student & faculty whitelist ($N \ge 1,800$ records).
- [ ] **5.2 Wi-Fi Outage Simulation:**
  - [ ] Wi-Fi router powered down.
  - [ ] Test RFID card tap (`A35F821B`) presented to reader.
  - [ ] Barrier opens in $< 150\text{ ms}$ using local LittleFS match.
  - [ ] Transaction queued locally into LittleFS offline log buffer.
- [ ] **5.3 Network Restoration & Auto-Flush:**
  - [ ] Wi-Fi router powered up.
  - [ ] ESP32 reconnects and automatically flushes buffered transactions to cloud database with zero dropped records.

---

## 6. Throughput & Morning Rush Stress Verification

- [ ] **6.1 Single-Lane Clearance Test:**
  - [ ] 30 consecutive card taps executed in under 60 seconds ($> 30\text{ persons/minute/lane}$).
  - [ ] Average tap-to-open latency measured at $< 180\text{ ms}$.
- [ ] **6.2 Anti-Rebound Verification:** Immediate re-tap on identical card within $1.5\text{ seconds}$ correctly rejected with 429 status code.
- [ ] **6.3 Inter-Gate Anti-Passback Test:**
  - [ ] Card tap at Library Gate followed by scan at Lara Gate within 15 seconds.
  - [ ] AI Anomaly Agent correctly flags `IMPOSSIBLE_VELOCITY` / `PASSBACK_VIOLATION`.

---

## 7. Pilot Sign-Off & Continuous 30-Day Monitoring

| Gate Name | Lead Commissioning Engineer | SOC Security Supervisor | Sign-Off Date | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Library Gate (Gate 3 - Pilot)** | `Eng. V. S. Murthy` | `Maj. R. K. Varma` | `2026-10-15` | **PASSED & COMMISSIONED** |
| **Lara Gate (Gate 2)** | `Eng. K. Anitha` | `Capt. M. Rao` | `2026-10-22` | **PASSED & COMMISSIONED** |
| **University Gate (Gate 1 - Main)** | `Eng. V. S. Murthy` | `Maj. R. K. Varma` | `2026-10-29` | **PASSED & COMMISSIONED** |

---
*Authorized by: Office of Campus Security & Infrastructure, Vignan University (VFSTR)*
