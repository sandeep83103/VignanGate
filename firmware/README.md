# Edge Controller Hardware & Firmware Guide: Vignan Smart Access

## 1. Overview
This module contains the physical computing firmware and hardware specifications for the **ESP32 Edge Gate Controller**, powering perimeter access points across **Vignan's Foundation for Science, Technology & Research (VFSTR)**.

The controller interfaces directly with an **RC522 13.56MHz RFID Reader**, high-voltage **Relay Module** (boom barrier actuation), dual-color **Status LEDs**, **Piezo Buzzer**, and an **Optical Beam-Break Sensor** for anti-tailgating.

---

## 2. Hardware Wiring & Pin Mapping

```
+-------------------------------------------------------------------------------+
|                             ESP32 Dev Module (30 Pin)                         |
+-------------------------------------------------------------------------------+
|  PIN NAME | CONNECTED PERIPHERAL       | PROTOCOL / FUNCTION                  |
|:---------:|:---------------------------|:-------------------------------------|
|  GPIO 5   | RC522 SDA / SS             | SPI Slave Select                     |
|  GPIO 18  | RC522 SCK                  | SPI Clock                            |
|  GPIO 23  | RC522 MOSI                 | SPI Master Out Slave In              |
|  GPIO 19  | RC522 MISO                 | SPI Master In Slave Out              |
|  GPIO 22  | RC522 RST                  | Hardware Reset                       |
|  3.3V     | RC522 3.3V                 | Power (DO NOT CONNECT TO 5V)         |
|  GND      | RC522 GND                  | Ground                               |
|-----------|----------------------------|--------------------------------------|
|  GPIO 26  | 5V Relay Input (IN1)       | Barrier Actuator Trigger (Active HIGH)|
|  GPIO 27  | Green Status LED           | Access Granted Visual Indicator      |
|  GPIO 12  | Red Status LED             | Access Denied / Alert Indicator      |
|  GPIO 14  | 5V Active Buzzer           | Auditory Access / Alarm Feedback     |
|  GPIO 34  | Optical Beam-Break Sensor  | Anti-Tailgating Sensor (Active LOW)  |
|  GPIO 35  | Fire Alarm Dry Contact     | Emergency Failsafe Open Interlock    |
+-------------------------------------------------------------------------------+
```

---

## 3. Bill of Materials (BOM)

| Component | Specification | Quantity | Purpose |
| :--- | :--- | :---: | :--- |
| **ESP32-WROOM-32** | 30-pin Dual-Core 240MHz Wi-Fi/BLE | 1 per lane | Master edge controller running FreeRTOS |
| **MFRC522 Module** | 13.56 MHz RFID Transceiver | 1 per lane | Contactless smart student/faculty card scanner |
| **5V Relay Module** | 1-Channel Optoisolated 10A 250VAC | 1 per lane | Electrical gate barrier motor triggering |
| **IR Beam Sensor** | E18-D80NK or Through-Beam Pair | 1 per lane | Detects vehicle transit and anti-tailgating |
| **Status LEDs** | 5mm High-Brightness (Green & Red) | 1 pair | Driver-facing visual go/no-go indicator |
| **Active Buzzer** | 5V Piezo | 1 | Guard/user auditory tone notification |
| **Power Supply** | 5V 2A DC Step-Down / MeanWell | 1 | Regulated power to ESP32 and Relay |

---

## 4. Software & Firmware Architecture

### 4.1 Dual-Core Multithreading (FreeRTOS)
The firmware leverages the ESP32's dual-core Xtensa processor:
- **Core 1 (`rfidScannerTask`):** High-priority (Priority 2) task dedicated to polling the SPI bus at 40Hz, anti-collision card identification, local debounce filtering, and relay pulsing.
- **Core 0 (`networkTelemetryTask`):** Background task (Priority 1) dedicated to Wi-Fi state management, TLS encryption, MQTT telemetry heartbeats, and message reception.
- **Inter-Task Communication:** Thread-safe FreeRTOS Queue (`xQueueCreate`) transfers parsed card UIDs from Core 1 to Core 0 with zero blocking.

### 4.2 Offline LittleFS Whitelist Survivability
If the campus Wi-Fi network drops:
1. Core 1 detects `!mqttClient.connected()`.
2. It queries the local in-memory index loaded from LittleFS (`/whitelist.json`).
3. If the card matches an authorized faculty/emergency credential, the barrier opens immediately ($< 15\text{ ms}$).
4. The event is queued to `/offline_queue.json` in flash memory.
5. When Wi-Fi reconnects, the queued records are automatically flushed to the central cloud server.

### 4.3 Hardware Watchdog Timer (WDT)
Configured for **8 seconds**. Both Core 0 and Core 1 tasks must routinely feed the watchdog (`esp_task_wdt_reset()`). If a network socket hangs or memory allocation freezes, the ESP32 executes an automatic hardware reset.

---

## 5. How to Compile & Flash

### Option A: Using PlatformIO (Recommended)
```bash
# Navigate to firmware directory
cd firmware

# Compile firmware
pio run

# Upload to connected ESP32 via USB
pio run --target upload

# Upload LittleFS filesystem data (whitelist.json)
pio run --target uploadfs

# Open serial monitor
pio devicemonitor -b 115200
```

### Option B: Using Arduino IDE
1. Install **ESP32 by Espressif Systems** via Boards Manager.
2. Install libraries:
   - `MFRC522` by GithubCommunity
   - `PubSubClient` by Nick O'Leary
   - `ArduinoJson` by Benoit Blanchon
3. Select Board: **ESP32 Dev Module**.
4. Open `esp32_gate_controller/esp32_gate_controller.ino` and click **Upload**.
