#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ==============================================================================
// VIGNAN SMART ACCESS — GATE CONTROLLER HARDWARE CONFIGURATION
// ==============================================================================

// Gate Identity Configuration
#define GATE_ID             "GATE-UG-01"
#define GATE_NAME           "University Gate (Main)"
#define GATE_SECTOR         "Sector A - Main Entrance"

// ------------------------------------------------------------------------------
// SPI Pin Mapping for RC522 RFID Module
// ------------------------------------------------------------------------------
#define RC522_SS_PIN        5     // Slave Select / SDA
#define RC522_RST_PIN       22    // Reset Pin
#define RC522_SCK_PIN       18    // SPI Serial Clock
#define RC522_MISO_PIN      19    // SPI Master In Slave Out
#define RC522_MOSI_PIN      23    // SPI Master Out Slave In

// ------------------------------------------------------------------------------
// Actuators, Feedback & Sensor Pin Mapping
// ------------------------------------------------------------------------------
#define BARRIER_RELAY_PIN   26    // 5V Relay triggering motorized boom barrier
#define LED_GREEN_PIN       27    // Status LED: Access Granted
#define LED_RED_PIN         12    // Status LED: Access Denied / Alert
#define BUZZER_PIN          14    // Piezo Buzzer for audio feedback
#define BEAM_SENSOR_PIN     34    // Optical Beam-Break Sensor (Anti-Tailgating)
#define FIRE_ALARM_PIN      35    // Emergency Fire Interlock (Active LOW)

// ------------------------------------------------------------------------------
// Timing & Operational Constants
// ------------------------------------------------------------------------------
#define BARRIER_OPEN_MS     3500  // Relay energize pulse duration (milliseconds)
#define HEARTBEAT_INTERVAL  5000  // Telemetry publish interval (milliseconds)
#define WDT_TIMEOUT_SEC     8     // Hardware Watchdog Timer timeout (seconds)
#define CARD_DEBOUNCE_MS    1500  // Minimum time between repeated scans on same card

// ------------------------------------------------------------------------------
// Network & MQTT Broker Defaults
// ------------------------------------------------------------------------------
#define WIFI_SSID           "VIGNAN_CAMPUS_IOT"
#define WIFI_PASSWORD       "VignanSecure@2026"
#define MQTT_BROKER         "mqtt.vignan.internal"
#define MQTT_PORT           1883
#define MQTT_CLIENT_ID      "ESP32-UG-001"

// MQTT Telemetry & Command Topics
#define TOPIC_TELEMETRY     "vignan/gates/" GATE_ID "/telemetry"
#define TOPIC_SCAN_EVENT    "vignan/gates/" GATE_ID "/scan"
#define TOPIC_BARRIER_CMD   "vignan/gates/" GATE_ID "/command"
#define TOPIC_SYNC_REQUEST  "vignan/gates/" GATE_ID "/sync"

#endif // CONFIG_H
