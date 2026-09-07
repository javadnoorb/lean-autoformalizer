import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # Lean 4 execution configuration
    USE_WSL: bool = os.getenv("USE_WSL", "true").lower() in ("true", "1", "yes")
    WSL_DISTRO: str = os.getenv("WSL_DISTRO", "Ubuntu")
    LEAN_BIN_WSL: str = os.getenv("LEAN_BIN_WSL", "~/.elan/bin/lean")
    LAKE_BIN_WSL: str = os.getenv("LAKE_BIN_WSL", "~/.elan/bin/lake")
    LEAN_BIN_LOCAL: str = os.getenv("LEAN_BIN_LOCAL", "lean")
    
    LEAN_TIMEOUT_SECS: int = int(os.getenv("LEAN_TIMEOUT_SECS", "15"))
    ALLOW_MOCK_FALLBACK: bool = os.getenv("ALLOW_MOCK_FALLBACK", "true").lower() in ("true", "1", "yes")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
