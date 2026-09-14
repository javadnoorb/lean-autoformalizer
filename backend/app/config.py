import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    # Total attempts (including the first) for a Gemini call that hits a
    # transient error (server overload, short-lived rate limit) before giving
    # up. Each retry is a billed API call, so this defaults to 1 (no retry --
    # fail straight to the mock fallback) -- raise it if you want retries and
    # are fine paying for the extra attempts.
    GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "1"))

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

    # Interactive (PyPantograph-backed) session limits. Unlike the rest of
    # this app, each interactive session holds a multi-GB resident process
    # across requests, so it needs real limits -- see
    # app/services/pantograph_sessions.py.
    INTERACTIVE_MAX_SESSIONS: int = int(os.getenv("INTERACTIVE_MAX_SESSIONS", "2"))
    INTERACTIVE_SESSION_IDLE_TIMEOUT_SECS: int = int(os.getenv("INTERACTIVE_SESSION_IDLE_TIMEOUT_SECS", "600"))
    INTERACTIVE_SESSION_SWEEP_INTERVAL_SECS: int = int(os.getenv("INTERACTIVE_SESSION_SWEEP_INTERVAL_SECS", "60"))
    INTERACTIVE_SESSION_START_TIMEOUT_SECS: int = int(os.getenv("INTERACTIVE_SESSION_START_TIMEOUT_SECS", "120"))
    # Every Pantograph call, across every session, is serialized through one
    # process-wide lock (see pantograph_sessions.py docstring for why). This
    # bounds how long a request queues for it before failing with a 503.
    INTERACTIVE_LOCK_WAIT_SECS: int = int(os.getenv("INTERACTIVE_LOCK_WAIT_SECS", "45"))
    INTERACTIVE_IMPORTS: str = os.getenv("INTERACTIVE_IMPORTS", "Mathlib")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
