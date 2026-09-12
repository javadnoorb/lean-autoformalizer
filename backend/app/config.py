import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # Lean 4 execution configuration
    LEAN_BIN: str = os.getenv("LEAN_BIN", "~/.elan/bin/lean")
    LAKE_BIN: str = os.getenv("LAKE_BIN", "~/.elan/bin/lake")

    # Path to a Lake project with Mathlib already built (its .lake/build contains
    # Mathlib.olean). When set, Lean code is run via `lake env lean` from inside
    # this directory so imports like `Mathlib.Tactic.Ring` resolve. Leave empty
    # to run bare `lean` with no extra library search path.
    LEAN_PROJECT_DIR: str = os.getenv("LEAN_PROJECT_DIR", "")

    LEAN_TIMEOUT_SECS: int = int(os.getenv("LEAN_TIMEOUT_SECS", "15"))
    ALLOW_MOCK_FALLBACK: bool = os.getenv("ALLOW_MOCK_FALLBACK", "true").lower() in ("true", "1", "yes")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
