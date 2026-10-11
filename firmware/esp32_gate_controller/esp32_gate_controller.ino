/**
 * ==============================================================================
 * VIGNAN SMART ACCESS — ESP32 GATE CONTROLLER FIRMWARE
 * Institution: Vignan's Foundation for Science, Technology & Research (VFSTR)
 * Author: Antigravity Agentic AI & Vignan Gate Project Team
 * Target Hardware: ESP32 Dev Module (WROOM-32) + RC522 RFID SPI Module
 * Architecture: FreeRTOS Dual-Core Multithreading (Core 1: Edge, Core 0: Network)
 * ==============================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <esp_task_wdt.h>
#include "config.h"
#include "offline_cache.h"

// ------------------------------------------------------------------------------
// Hardware Instances & Network Clients
// ------------------------------------------------------------------------------
MFRC522 rfid(RC522_SS_PIN, RC522_RST_PIN);
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// ------------------------------------------------------------------------------
// FreeRTOS Thread Synchronization
// ------------------------------------------------------------------------------
struct ScanEvent {
    char cardUid[32];
    uint32_t timestamp;
};

static QueueHandle_t rfidEventQueue = NULL;
static TaskHandle_t rfidTaskHandle = NULL;
static TaskHandle_t networkTaskHandle = NULL;

// ------------------------------------------------------------------------------
// Non-Blocking Actuation & Sensor State
// ------------------------------------------------------------------------------
volatile bool barrierIsOpen = false;
unsigned long barrierOpenedAt = 0;
String lastScannedUid = "";
unsigned long lastScanMillis = 0;
volatile bool tailgatingDetected = false;
volatile bool emergencyEvacuationActive = false;

// ------------------------------------------------------------------------------
// Interrupt Service Routine for Beam-Break Anti-Tailgating Sensor
// ------------------------------------------------------------------------------
void IRAM_ATTR onBeamBreakChange() {
    int beamState = digitalRead(BEAM_SENSOR_PIN);
    if (beamState == LOW && !barrierIsOpen && !emergencyEvacuationActive) {
        // Beam broken while barrier is legally closed -> Possible perimeter breach / tailgating
        tailgatingDetected = true;
    }
}

// ------------------------------------------------------------------------------
// Interrupt Service Routine for Fire Alarm Emergency Interlock (GPIO 35)
// ------------------------------------------------------------------------------
void IRAM_ATTR onFireAlarmTrigger() {
    int fireState = digitalRead(FIRE_ALARM_PIN);
    if (fireState == LOW) {
        // Active LOW dry-contact closed: Fire emergency in progress
        emergencyEvacuationActive = true;
        barrierIsOpen = true;
        digitalWrite(BARRIER_RELAY_PIN, HIGH); // Fail-safe: Force barrier open
        digitalWrite(LED_GREEN_PIN, HIGH);
        digitalWrite(LED_RED_PIN, HIGH);     // Visual evacuation signal
    } else {
        // Normal contact restored
        emergencyEvacuationActive = false;
    }
}

// ------------------------------------------------------------------------------
// Helper: Hardware Feedback (LEDs, Relay, Buzzer)
// ------------------------------------------------------------------------------
void triggerBarrierOpen(const char* reason) {
    Serial.printf("[Actuator] BARRIER OPEN commanded: %s\n", reason);
    digitalWrite(BARRIER_RELAY_PIN, HIGH); // Energize relay
    digitalWrite(LED_GREEN_PIN, HIGH);
    digitalWrite(LED_RED_PIN, LOW);
    
    // Quick double beep
    digitalWrite(BUZZER_PIN, HIGH); delay(60); digitalWrite(BUZZER_PIN, LOW);
    delay(40);
    digitalWrite(BUZZER_PIN, HIGH); delay(60); digitalWrite(BUZZER_PIN, LOW);

    barrierIsOpen = true;
    barrierOpenedAt = millis();
}

void triggerAccessDenied(const char* reason) {
    Serial.printf("[Actuator] ACCESS DENIED: %s\n", reason);
    digitalWrite(LED_RED_PIN, HIGH);
    digitalWrite(LED_GREEN_PIN, LOW);
    
    // Warning buzz
    digitalWrite(BUZZER_PIN, HIGH); delay(350); digitalWrite(BUZZER_PIN, LOW);
    
    delay(500);
    digitalWrite(LED_RED_PIN, LOW);
}

void updateBarrierState() {
    // If fire emergency is active, fail-safe rule prevents barrier from closing
    if (emergencyEvacuationActive) {
        digitalWrite(BARRIER_RELAY_PIN, HIGH);
        digitalWrite(LED_GREEN_PIN, HIGH);
        digitalWrite(LED_RED_PIN, HIGH);
        barrierIsOpen = true;
        return;
    }

    if (barrierIsOpen && (millis() - barrierOpenedAt >= BARRIER_OPEN_MS)) {
        digitalWrite(BARRIER_RELAY_PIN, LOW); // De-energize relay (Barrier drops)
        digitalWrite(LED_GREEN_PIN, LOW);
        barrierIsOpen = false;
        Serial.println("[Actuator] Barrier auto-closed (Cycle complete).");
    }
}

// ------------------------------------------------------------------------------
// TASK 1 (Core 1): High-Speed RFID Polling & Local Fallback Logic
// ------------------------------------------------------------------------------
void rfidScannerTask(void* pvParameters) {
    Serial.println("[Core 1] RFID Scanner Task running...");
    SPI.begin(RC522_SCK_PIN, RC522_MISO_PIN, RC522_MOSI_PIN, RC522_SS_PIN);
    rfid.PCD_Init();
    delay(50);
    rfid.PCD_DumpVersionToSerial();

    for (;;) {
        // Feed task watchdog
        esp_task_wdt_reset();

        updateBarrierState();

        // Check if a new RFID card is presented
        if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
            String uidStr = "";
            for (byte i = 0; i < rfid.uid.size; i++) {
                if (rfid.uid.uidByte[i] < 0x10) uidStr += "0";
                uidStr += String(rfid.uid.uidByte[i], HEX);
            }
            uidStr.toUpperCase();

            // Anti-bounce check
            if (uidStr != lastScannedUid || (millis() - lastScanMillis > CARD_DEBOUNCE_MS)) {
                lastScannedUid = uidStr;
                lastScanMillis = millis();

                Serial.printf("\n[RFID Tap] Detected UID: %s\n", uidStr.c_str());

                // Check online status
                if (mqttClient.connected()) {
                    // Send to Core 0 Network Queue
                    ScanEvent evt;
                    strncpy(evt.cardUid, uidStr.c_str(), sizeof(evt.cardUid) - 1);
                    evt.timestamp = millis();
                    xQueueSend(rfidEventQueue, &evt, 0);
                    Serial.println("[Core 1] Pushed scan event to network queue.");
                } else {
                    // Offline Fallback Mode
                    Serial.println("[Core 1] Network Offline! Evaluating via LittleFS cache...");
                    WhitelistEntry matched;
                    if (CacheManager.isAuthorized(uidStr, matched)) {
                        Serial.printf("[Core 1] Whitelist Match: %s (%s). Granting entry.\n", matched.fullName.c_str(), matched.role.c_str());
                        triggerBarrierOpen("Offline Whitelist Verified");
                        CacheManager.recordOfflineScan(uidStr, "GRANTED_OFFLINE", String(millis()));
                    } else {
                        Serial.println("[Core 1] UID not in offline whitelist. Denying access.");
                        triggerAccessDenied("Offline Unregistered UID");
                        CacheManager.recordOfflineScan(uidStr, "DENIED_OFFLINE", String(millis()));
                    }
                }
            }

            rfid.PICC_HaltA();
            rfid.PCD_StopCrypto1();
        }

        vTaskDelay(pdMS_TO_TICKS(25)); // 40Hz polling rate
    }
}

// ------------------------------------------------------------------------------
// MQTT Inbound Command Callback
// ------------------------------------------------------------------------------
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
    String msg = "";
    for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
    Serial.printf("[MQTT Inbound] Topic: %s | Payload: %s\n", topic, msg.c_str());

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, msg);
    if (!err) {
        const char* action = doc["action"];
        if (action && strcmp(action, "OPEN_BARRIER") == 0) {
            triggerBarrierOpen("Remote Cloud AI Command");
        } else if (action && strcmp(action, "LOCK_BARRIER") == 0) {
            triggerAccessDenied("Remote Security Lock Command");
        }
    }
}

// ------------------------------------------------------------------------------
// TASK 2 (Core 0): Wi-Fi Management, MQTT Telemetry & Cloud Sync
// ------------------------------------------------------------------------------
void networkTelemetryTask(void* pvParameters) {
    Serial.println("[Core 0] Network Telemetry Task running...");
    unsigned long lastHeartbeat = 0;

    for (;;) {
        // Feed task watchdog
        esp_task_wdt_reset();

        // Ensure Wi-Fi Connectivity
        if (WiFi.status() != WL_CONNECTED) {
            Serial.printf("[Wi-Fi] Connecting to %s...\n", WIFI_SSID);
            WiFi.mode(WIFI_STA);
            WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
            unsigned long startAttempt = millis();
            while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 8000) {
                vTaskDelay(pdMS_TO_TICKS(500));
            }
            if (WiFi.status() == WL_CONNECTED) {
                Serial.printf("[Wi-Fi] Connected! IP: %s (RSSI: %d dBm)\n", 
                              WiFi.localIP().toString().c_str(), WiFi.RSSI());
            }
        }

        // Ensure MQTT Connectivity
        if (WiFi.status() == WL_CONNECTED) {
            if (!mqttClient.connected()) {
                mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
                mqttClient.setCallback(onMqttMessage);
                Serial.println("[MQTT] Connecting to Broker...");
                if (mqttClient.connect(MQTT_CLIENT_ID)) {
                    Serial.println("[MQTT] Connected to Broker!");
                    mqttClient.subscribe(TOPIC_BARRIER_CMD);

                    // Flush queued offline logs upon reconnect
                    String queued = CacheManager.getAndClearPendingEvents();
                    if (queued != "[]") {
                        mqttClient.publish(TOPIC_SYNC_REQUEST, queued.c_str());
                        Serial.println("[MQTT] Flushed offline queued events to server.");
                    }
                }
            } else {
                mqttClient.loop();
            }
        }

        // Dequeue RFID tap events from Core 1
        ScanEvent evt;
        if (xQueueReceive(rfidEventQueue, &evt, 0) == pdTRUE) {
            if (mqttClient.connected()) {
                JsonDocument doc;
                doc["gate_id"] = GATE_ID;
                doc["card_uid"] = evt.cardUid;
                doc["method"] = "RFID";
                doc["device_timestamp"] = evt.timestamp;
                doc["rssi"] = WiFi.RSSI();

                char buffer[256];
                serializeJson(doc, buffer);
                mqttClient.publish(TOPIC_SCAN_EVENT, buffer);
                Serial.printf("[MQTT Outbound] Published Scan: %s\n", buffer);
            }
        }

        // Periodic Telemetry Heartbeat (every 5 seconds)
        if (millis() - lastHeartbeat >= HEARTBEAT_INTERVAL) {
            lastHeartbeat = millis();
            if (mqttClient.connected()) {
                JsonDocument doc;
                doc["device_id"] = MQTT_CLIENT_ID;
                doc["gate"] = GATE_NAME;
                doc["status"] = "ONLINE";
                doc["signal_percent"] = constrain(map(WiFi.RSSI(), -90, -30, 0, 100), 0, 100);
                doc["barrier_state"] = barrierIsOpen ? "OPEN" : "CLOSED";
                doc["tailgating_flag"] = tailgatingDetected;
                doc["emergency_evacuation"] = emergencyEvacuationActive;
                doc["cached_whitelist"] = CacheManager.getCachedEntryCount();
                doc["free_heap"] = ESP.getFreeHeap();
                doc["uptime_sec"] = millis() / 1000;

                char buffer[384];
                serializeJson(doc, buffer);
                mqttClient.publish(TOPIC_TELEMETRY, buffer);
                tailgatingDetected = false; // Reset after reporting
            }
        }

        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

// ------------------------------------------------------------------------------
// SETUP
// ------------------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("\n=======================================================");
    Serial.println("  VIGNAN SMART ACCESS — GATE EDGE FIRMWARE BOOTING     ");
    Serial.println("=======================================================");

    // Pin Modes
    pinMode(BARRIER_RELAY_PIN, OUTPUT);
    pinMode(LED_GREEN_PIN, OUTPUT);
    pinMode(LED_RED_PIN, OUTPUT);
    pinMode(BUZZER_PIN, OUTPUT);
    pinMode(BEAM_SENSOR_PIN, INPUT_PULLUP);
    pinMode(FIRE_ALARM_PIN, INPUT_PULLUP);

    // Initial safe states
    digitalWrite(BARRIER_RELAY_PIN, LOW); // Fail-secure closed
    digitalWrite(LED_GREEN_PIN, LOW);
    digitalWrite(LED_RED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);

    // Initialize LittleFS Offline Whitelist Cache
    CacheManager.begin();

    // Attach Interrupt for Optical Beam-Break Sensor
    attachInterrupt(digitalPinToInterrupt(BEAM_SENSOR_PIN), onBeamBreakChange, CHANGE);

    // Attach Interrupt for Fire Alarm Emergency Interlock (GPIO 35 Active LOW)
    attachInterrupt(digitalPinToInterrupt(FIRE_ALARM_PIN), onFireAlarmTrigger, CHANGE);

    // Initialize Hardware Watchdog Timer (8 sec timeout)
    esp_task_wdt_init(WDT_TIMEOUT_SEC, true);

    // Create FreeRTOS Event Queue
    rfidEventQueue = xQueueCreate(10, sizeof(ScanEvent));

    // Spawn Multithreaded FreeRTOS Tasks
    // Task 1: RFID polling pinned to Core 1 (High priority)
    xTaskCreatePinnedToCore(
        rfidScannerTask,
        "RFID_Core1",
        4096,
        NULL,
        2, // Priority 2
        &rfidTaskHandle,
        1  // Core 1
    );

    // Task 2: Network & MQTT pinned to Core 0
    xTaskCreatePinnedToCore(
        networkTelemetryTask,
        "Net_Core0",
        8192,
        NULL,
        1, // Priority 1
        &networkTaskHandle,
        0  // Core 0
    );

    esp_task_wdt_add(rfidTaskHandle);
    esp_task_wdt_add(networkTaskHandle);

    Serial.println("[Boot] FreeRTOS tasks spawned across Core 0 and Core 1.");
}

void loop() {
    // Empty: Task execution is fully managed by FreeRTOS scheduler
    vTaskDelete(NULL);
}
