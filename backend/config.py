from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "VIGNAN SMART ACCESS API"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./vignan_gate.db"
    
    # Anti-Rebound (Double-tap prevention window in seconds)
    ANTI_REBOUND_SECONDS: float = 1.5
    
    # Active Campus Gates
    CAMPUS_GATES: List[str] = [
        "University Gate",
        "Lara Gate",
        "Library Gate"
    ]
    
    # MQTT Configuration
    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_KEEPALIVE: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()
