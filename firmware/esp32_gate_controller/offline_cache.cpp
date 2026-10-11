#include "offline_cache.h"

OfflineCacheManager CacheManager;

OfflineCacheManager::OfflineCacheManager() {
    _whitelist.reserve(100);
}

bool OfflineCacheManager::begin() {
    if (!LittleFS.begin(true)) {
        Serial.println("[LittleFS] ERROR: Mounting failed. Formatting attempted.");
        return false;
    }
    Serial.println("[LittleFS] Mounted successfully.");
    return loadWhitelistFromFlash();
}

bool OfflineCacheManager::loadWhitelistFromFlash() {
    _whitelist.clear();

    if (!LittleFS.exists(WHITELIST_PATH)) {
        Serial.println("[LittleFS] Whitelist file not found. Creating default offline entries.");
        // Seed default emergency personnel and faculty
        File f = LittleFS.open(WHITELIST_PATH, "w");
        if (f) {
            JsonDocument doc;
            JsonArray arr = doc.to<JsonArray>();
            
            JsonObject u1 = arr.add<JsonObject>();
            u1["uid"] = "A35F821B";
            u1["pid"] = "STU20261245";
            u1["name"] = "Rahul Kumar";
            u1["role"] = "Student";
            u1["auth"] = true;

            JsonObject u2 = arr.add<JsonObject>();
            u2["uid"] = "C48A109E";
            u2["pid"] = "FAC10421";
            u2["name"] = "Dr. Priya Rao";
            u2["role"] = "Faculty";
            u2["auth"] = true;

            JsonObject u3 = arr.add<JsonObject>();
            u3["uid"] = "FF12E844";
            u3["pid"] = "SEC001";
            u3["name"] = "Security Chief";
            u3["role"] = "Security";
            u3["auth"] = true;

            serializeJson(doc, f);
            f.close();
        }
    }

    File file = LittleFS.open(WHITELIST_PATH, "r");
    if (!file) {
        Serial.println("[LittleFS] Failed to open whitelist for reading.");
        return false;
    }

    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, file);
    file.close();

    if (error) {
        Serial.printf("[LittleFS] JSON parse failed: %s\n", error.c_str());
        return false;
    }

    JsonArray array = doc.as<JsonArray>();
    for (JsonObject obj : array) {
        WhitelistEntry entry;
        entry.cardUid = obj["uid"].as<String>();
        entry.personId = obj["pid"].as<String>();
        entry.fullName = obj["name"].as<String>();
        entry.role = obj["role"].as<String>();
        entry.isAuthorized = obj["auth"].as<bool>();
        _whitelist.push_back(entry);
    }

    Serial.printf("[LittleFS] Loaded %d cached credentials into fast RAM index.\n", _whitelist.size());
    return true;
}

bool OfflineCacheManager::isAuthorized(const String& scannedUid, WhitelistEntry& matchedEntry) {
    for (const auto& entry : _whitelist) {
        if (entry.cardUid.equalsIgnoreCase(scannedUid)) {
            matchedEntry = entry;
            return entry.isAuthorized;
        }
    }
    return false;
}

bool OfflineCacheManager::recordOfflineScan(const String& cardUid, const String& decision, const String& timestamp) {
    JsonDocument doc;
    if (LittleFS.exists(OFFLINE_LOG_PATH)) {
        File readLog = LittleFS.open(OFFLINE_LOG_PATH, "r");
        if (readLog) {
            deserializeJson(doc, readLog);
            readLog.close();
        }
    }

    JsonArray logs = doc.as<JsonArray>();
    if (logs.isNull()) {
        logs = doc.to<JsonArray>();
    }

    JsonObject item = logs.add<JsonObject>();
    item["uid"] = cardUid;
    item["decision"] = decision;
    item["timestamp"] = timestamp;
    item["mode"] = "OFFLINE_CACHE";

    File writeLog = LittleFS.open(OFFLINE_LOG_PATH, "w");
    if (!writeLog) return false;
    serializeJson(doc, writeLog);
    writeLog.close();
    return true;
}

String OfflineCacheManager::getAndClearPendingEvents() {
    if (!LittleFS.exists(OFFLINE_LOG_PATH)) return "[]";
    
    File logFile = LittleFS.open(OFFLINE_LOG_PATH, "r");
    if (!logFile) return "[]";

    String payload = logFile.readString();
    logFile.close();

    // Clear after reading
    LittleFS.remove(OFFLINE_LOG_PATH);
    return payload;
}

size_t OfflineCacheManager::getCachedEntryCount() const {
    return _whitelist.size();
}
