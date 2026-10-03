"""PyPantograph-backed interactive Lean tactic-search sessions.

Unlike lean_runner.py (spawn a fresh `lean` process per call, throw it
away), this keeps a live Lean+Mathlib process per session so tactics can
be applied one at a time against a persistent goal state -- the primitive
real interactive/tree search needs.

Soft dependency, same shape as leandojo_harness.py: `pantograph` is NOT in
requirements.txt and is not installable via a stock `pip install
pantograph` for this project. The published package's bundled Lean
toolchain can drift out of sync with its own Lean-side source (see
.claude/skills/lean-interactive-search/SKILL.md for the full story) --
what actually works here is a local clone with its `src` submodule
manually re-pointed to leanprover/Pantograph commit
92d4818a4b343d7be293731e03359a19e8082626 (matches this project's
`lean-toolchain`, v4.33.1), then `pip install` from that clone. See
deploy/pantograph-bench-remote.sh for the exact recipe. Without that
install, this module reports itself unavailable and degrades gracefully,
exactly like leandojo_harness.py does for lean_dojo.

Key correctness constraint (verified against the installed PyPantograph
source, not assumed): its sync methods (`goal_start`, `goal_tactic`,
`restart`, ...) are `to_sync(...)`-wrapped coroutines sharing ONE asyncio
event loop, captured once at import time and reused by every `Server`
instance for the life of the process. asyncio event loops are not safe to
drive from multiple threads at once, and FastAPI runs sync route handlers
in a thread pool -- so every call into Pantograph, across every session,
must be serialized through a single process-wide lock. This is not an
optimization to relax later; two concurrent sessions calling in from
different threads without it is a real correctness bug, not just a
performance concern.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class InteractiveUnavailableError(RuntimeError):
    """pantograph is not installed in this environment."""


class InteractiveCapacityError(RuntimeError):
    """Max concurrent interactive sessions already reached."""


class InteractiveSessionNotFoundError(RuntimeError):
    """No active session with the given id."""


class InteractiveEngineBusyError(RuntimeError):
    """Timed out waiting for the process-wide Pantograph lock."""


class InteractiveSessionCrashedError(RuntimeError):
    """The underlying pantograph-repl process for this session died."""


class InteractiveStatementError(RuntimeError):
    """goal_start rejected the given statement."""


@dataclass
class _Session:
    id: str
    server: Any  # pantograph.server.Server
    state: Any  # pantograph.expr.GoalState (last known-good)
    statement: str
    theorem_name: Optional[str]
    created_at: float
    last_used_at: float


class PantographSessionManager:
    def __init__(self):
        self.available = False
        self._server_cls = None
        self._Site = None
        self._TacticFailure = None
        self._ServerError = None
        self._get_lean_path = None
        self._check_availability()

        self._sessions: Dict[str, _Session] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._sweeper_thread: Optional[threading.Thread] = None

    def _check_availability(self) -> None:
        try:
            from pantograph.server import Server
            from pantograph.expr import Site
            from pantograph.message import ServerError, TacticFailure
            from pantograph.utils import get_lean_path

            self._server_cls = Server
            self._Site = Site
            self._TacticFailure = TacticFailure
            self._ServerError = ServerError
            self._get_lean_path = get_lean_path
            self.available = True
            logger.info("pantograph is successfully imported.")
        except ImportError:
            self.available = False
            logger.info(
                "pantograph is not installed; interactive session API will report unavailable."
            )

    def _get_project_dir(self) -> str:
        """Same resolution as lean_runner._get_project_dir(): reuse the
        already-configured Mathlib Lake project, or '' if unset/missing."""
        import os

        if not settings.LEAN_PROJECT_DIR:
            return ""
        expanded = os.path.expanduser(settings.LEAN_PROJECT_DIR)
        return expanded if os.path.isdir(expanded) else ""

    def get_status(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "description": (
                "PyPantograph interactive session API for incremental tactic application."
                if self.available
                else "pantograph package not installed in current Python environment."
            ),
            "active_sessions": len(self._sessions),
            "max_sessions": settings.INTERACTIVE_MAX_SESSIONS,
            "idle_timeout_secs": settings.INTERACTIVE_SESSION_IDLE_TIMEOUT_SECS,
        }

    def _acquire_lock(self):
        acquired = self._lock.acquire(timeout=settings.INTERACTIVE_LOCK_WAIT_SECS)
        if not acquired:
            raise InteractiveEngineBusyError(
                "interactive engine is busy handling another request, try again shortly"
            )

    def _create_server(self, project_dir: str, imports: List[str], start_timeout: int):
        server = self._server_cls(
            imports=imports,
            project_path=project_dir or None,
            timeout=start_timeout,
            _sync_init=False,
        )
        if project_dir:
            server.lean_path = self._get_lean_path(project_dir)
        try:
            server.restart()
        except Exception:
            self._force_close(server)
            raise
        return server

    @staticmethod
    def _force_close(server) -> None:
        """server.__del__ is a no-op in PyPantograph -- nothing closes the
        underlying pantograph-repl process automatically. _close() only
        sends SIGTERM; kill() is the stronger fallback."""
        try:
            server._close()
        except Exception:
            pass
        if getattr(server, "proc", None) is not None:
            try:
                server.proc.kill()
            except Exception:
                pass

    def start_session(self, statement: str, theorem_name: Optional[str] = None) -> Dict[str, Any]:
        if not self.available:
            raise InteractiveUnavailableError("pantograph is not installed in this environment")

        self._acquire_lock()
        try:
            self._evict_idle_locked()
            if len(self._sessions) >= settings.INTERACTIVE_MAX_SESSIONS:
                raise InteractiveCapacityError(
                    f"max concurrent interactive sessions ({settings.INTERACTIVE_MAX_SESSIONS}) reached"
                )

            project_dir = self._get_project_dir()
            imports = [s.strip() for s in settings.INTERACTIVE_IMPORTS.split(",") if s.strip()]
            server = self._create_server(
                project_dir, imports, settings.INTERACTIVE_SESSION_START_TIMEOUT_SECS
            )

            try:
                state = server.goal_start(statement)
            except Exception as e:
                self._force_close(server)
                raise InteractiveStatementError(str(e)) from e

            sid = f"sess_{uuid.uuid4().hex[:12]}"
            now = time.time()
            self._sessions[sid] = _Session(
                id=sid,
                server=server,
                state=state,
                statement=statement,
                theorem_name=theorem_name,
                created_at=now,
                last_used_at=now,
            )
            self._ensure_sweeper_started_locked()
            return {
                "session_id": sid,
                "goals": [str(g) for g in state.goals],
                "is_solved": state.is_solved,
            }
        finally:
            self._lock.release()

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        self._acquire_lock()
        try:
            session = self._sessions.get(session_id)
            if session is None:
                raise InteractiveSessionNotFoundError(session_id)
            return {
                "session_id": session.id,
                "goals": [str(g) for g in session.state.goals],
                "is_solved": session.state.is_solved,
            }
        finally:
            self._lock.release()

    def apply_tactic(
        self, session_id: str, tactic: str, goal_id: Optional[int] = None
    ) -> Dict[str, Any]:
        self._acquire_lock()
        try:
            session = self._sessions.get(session_id)
            if session is None:
                raise InteractiveSessionNotFoundError(session_id)

            site = self._Site(goal_id=goal_id) if goal_id is not None else self._Site()
            t0 = time.time()
            try:
                new_state = session.server.goal_tactic(session.state, tactic=tactic, site=site)
                session.state = new_state
                session.last_used_at = time.time()
                return {
                    "status": "success",
                    "message": None,
                    "remaining_goals": [str(g) for g in new_state.goals],
                    "is_solved": new_state.is_solved,
                    "duration_ms": int((time.time() - t0) * 1000),
                }
            except self._TacticFailure as e:
                session.last_used_at = time.time()
                return {
                    "status": "failed",
                    "message": str(e),
                    "remaining_goals": [str(g) for g in session.state.goals],
                    "is_solved": False,
                    "duration_ms": int((time.time() - t0) * 1000),
                }
            except self._ServerError as e:
                if getattr(session.server, "proc", None) is None:
                    self._sessions.pop(session_id, None)
                    raise InteractiveSessionCrashedError(str(e)) from e
                session.last_used_at = time.time()
                return {
                    "status": "failed",
                    "message": str(e),
                    "remaining_goals": [str(g) for g in session.state.goals],
                    "is_solved": False,
                    "duration_ms": int((time.time() - t0) * 1000),
                }
        finally:
            self._lock.release()

    def close_session(self, session_id: str) -> bool:
        self._acquire_lock()
        try:
            return self._close_session_locked(session_id)
        finally:
            self._lock.release()

    def _close_session_locked(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        self._force_close(session.server)
        return True

    def _evict_idle_locked(self) -> None:
        now = time.time()
        stale = [
            sid
            for sid, s in self._sessions.items()
            if now - s.last_used_at > settings.INTERACTIVE_SESSION_IDLE_TIMEOUT_SECS
        ]
        for sid in stale:
            logger.info("Evicting idle interactive session %s", sid)
            self._close_session_locked(sid)

    def _ensure_sweeper_started_locked(self) -> None:
        if self._sweeper_thread is None:
            self._sweeper_thread = threading.Thread(target=self._sweep_loop, daemon=True)
            self._sweeper_thread.start()

    def _sweep_loop(self) -> None:
        interval = settings.INTERACTIVE_SESSION_SWEEP_INTERVAL_SECS
        while not self._stop_event.wait(interval):
            if self._lock.acquire(timeout=1):
                try:
                    self._evict_idle_locked()
                finally:
                    self._lock.release()
            # else: a real request is in flight; skip this round, try again next interval.

    def shutdown(self) -> None:
        """Close every remaining session. Call on app shutdown -- an
        idle-but-alive Pantograph process is exactly the kind of orphan
        lean_runner.kill_all_active() exists to prevent, just heavier."""
        self._stop_event.set()
        with self._lock:
            for sid in list(self._sessions):
                self._close_session_locked(sid)
        if self._sweeper_thread is not None:
            self._sweeper_thread.join(timeout=5)


pantograph_sessions = PantographSessionManager()
