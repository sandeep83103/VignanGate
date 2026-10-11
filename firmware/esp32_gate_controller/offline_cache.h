#ifndef OFFLINE_CACHE_H
#define OFFLINE_CACHE_H

#include <Arduino.h>
#include <vector>
#include <LittleFS.h>
#include <ArduinoJson.h>

struct WhitelistEntry {
    String cardUid;
    String personId;
    String fullName;
    String role;
    bool isAuthorized;
};

class OfflineCacheManager {
public:
    OfflineCacheManager();
    
    // Initialize LittleFS and populate in-memory whitelist index
    bool begin();
    
    // Fast O(N) in-memory lookup (< 2ms)
    bool isAuthorized(const String& scannedUid, WhitelistEntry& matchedEntry);
    
    // Queue offline scan events during network disconnection
    bool recordOfflineScan(const String& cardUid, const String& decision, const String& timestamp);
    
    // Read and clear queued offline events when network reconnects
    String getAndClearPendingEvents();
    
    // Get total cached whitelist entries
    size_t getCachedEntryCount() const;

private:
    std::vector<WhitelistEntry> _whitelist;
    const char* WHITELIST_PATH = "/whitelist.json";
    const char* OFFLINE_LOG_PATH = "/offline_queue.json";
    
    bool loadWhitelistFromFlash();
};

extern OfflineCacheManager CacheManager;

#endif // OFFLINE_CACHE_H
