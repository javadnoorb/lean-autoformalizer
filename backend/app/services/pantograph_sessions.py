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
            status, payload = self._apply_tactic_step(session, session.state, tactic, site)
            session.last_used_at = time.time()
            duration_ms = int((time.time() - t0) * 1000)

            if status == "success":
                new_state = payload
                session.state = new_state
                return {
                    "status": "success",
                    "message": None,
                    "remaining_goals": [str(g) for g in new_state.goals],
                    "is_solved": new_state.is_solved,
                    "duration_ms": duration_ms,
                }
            return {
                "status": "failed",
                "message": payload,
                "remaining_goals": [str(g) for g in session.state.goals],
                "is_solved": False,
                "duration_ms": duration_ms,
            }
        finally:
            self._lock.release()

    def run_search(
        self,
        session_id: str,
        max_depth: Optional[int] = None,
        max_attempts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Bounded depth-first proof search with backtracking, automating
        what apply_tactic previously required a human/test client to drive
        one call at a time (see .claude/skills/lean-interactive-search/SKILL.md).
        At each goal state, tries INTERACTIVE_SEARCH_TACTICS in order; a
        tactic that succeeds without solving recurses one level deeper,
        bounded by max_depth. Backtracking is free -- PyPantograph GoalStates
        are immutable snapshots, so trying the next tactic against the same
        parent state after a dead end is a normal goal_tactic call, not an
        undo.

        Held as a single critical section for the whole search, unlike
        apply_tactic's one-call-per-lock-acquisition. Releasing the lock
        between attempts would let a concurrent apply_tactic() on this same
        session commit a state this search's backtracking doesn't know
        about -- exactly the kind of race the module docstring's locking
        constraint exists to rule out. With the default bounds (depth 6, 40
        attempts) and typical sub-second tactic latency this finishes well
        inside INTERACTIVE_LOCK_WAIT_SECS; other interactive requests queue
        behind it like they would behind any other in-flight call.

        Exploring a losing branch never touches session.state -- only a
        solving path is committed, mirroring apply_tactic's failure
        semantics.
        """
        self._acquire_lock()
        try:
            session = self._sessions.get(session_id)
            if session is None:
                raise InteractiveSessionNotFoundError(session_id)

            depth_budget = (
                max_depth if max_depth is not None else settings.INTERACTIVE_SEARCH_MAX_DEPTH
            )
            attempt_budget = (
                max_attempts if max_attempts is not None else settings.INTERACTIVE_SEARCH_MAX_ATTEMPTS
            )
            tactics = [t.strip() for t in settings.INTERACTIVE_SEARCH_TACTICS.split(",") if t.strip()]

            t0 = time.time()
            trace: List[Dict[str, Any]] = []
            attempts = [0]
            found = self._dfs(session, session.state, tactics, depth_budget, attempt_budget, attempts, trace, [])
            duration_ms = int((time.time() - t0) * 1000)
            session.last_used_at = time.time()

            if found is not None:
                path, final_state = found
                session.state = final_state
                return {
                    "session_id": session_id,
                    "success": True,
                    "is_solved": final_state.is_solved,
                    "tactics": path,
                    "remaining_goals": [str(g) for g in final_state.goals],
                    "attempts": attempts[0],
                    "duration_ms": duration_ms,
                    "trace": trace,
                }

            return {
                "session_id": session_id,
                "success": False,
                "is_solved": False,
                "tactics": [],
                "remaining_goals": [str(g) for g in session.state.goals],
                "attempts": attempts[0],
                "duration_ms": duration_ms,
                "trace": trace,
            }
        finally:
            self._lock.release()

    def _dfs(
        self,
        session: "_Session",
        state: Any,
        tactics: List[str],
        depth_left: int,
        attempt_budget: int,
        attempts: List[int],
        trace: List[Dict[str, Any]],
        path: List[str],
    ):
        """Assumes self._lock is already held by run_search. Returns
        (winning_tactic_path, solved_state) or None if no path was found
        within the remaining depth/attempt budget."""
        if state.is_solved:
            return path, state

        if depth_left <= 0:
            return None

        for tactic in tactics:
            if attempts[0] >= attempt_budget:
                return None
            attempts[0] += 1

            site = self._Site(goal_id=0) if len(state.goals) > 1 else self._Site()
            status, payload = self._apply_tactic_step(session, state, tactic, site)
            if status == "success":
                new_state = payload
                trace.append({
                    "depth": len(path),
                    "tactic": tactic,
                    "status": "success",
                    "message": None,
                    "remaining_goals": [str(g) for g in new_state.goals],
                })
                result = self._dfs(
                    session, new_state, tactics, depth_left - 1, attempt_budget, attempts, trace, path + [tactic]
                )
                if result is not None:
                    return result
                # Dead end past this point -- backtrack and try the next
                # tactic against the same `state` above.
            else:
                trace.append({
                    "depth": len(path),
                    "tactic": tactic,
                    "status": "failed",
                    "message": payload,
                    "remaining_goals": [str(g) for g in state.goals],
                })

        return None

    def _apply_tactic_step(self, session: "_Session", state: Any, tactic: str, site: Any):
        """A single goal_tactic call, assuming self._lock is already held.
        Returns ("success", new_state) or ("failed", message); raises
        InteractiveSessionCrashedError (and evicts the session) exactly
        like apply_tactic does on a dead-process ServerError. Shared by
        apply_tactic and the search's _dfs -- site selection stays with each
        caller since they pick goals differently (apply_tactic: whatever the
        API caller asked for; search: always the first remaining goal)."""
        try:
            new_state = session.server.goal_tactic(state, tactic=tactic, site=site)
            return "success", new_state
        except self._TacticFailure as e:
            return "failed", str(e)
        except self._ServerError as e:
            if getattr(session.server, "proc", None) is None:
                self._sessions.pop(session.id, None)
                raise InteractiveSessionCrashedError(str(e)) from e
            return "failed", str(e)

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
