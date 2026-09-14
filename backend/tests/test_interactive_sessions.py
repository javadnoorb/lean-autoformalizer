"""Tests for the PyPantograph-backed interactive session manager.

`pantograph` is a soft dependency (see pantograph_sessions.py) that isn't
installed in this dev/CI environment -- these tests exercise the manager's
own bookkeeping logic (limits, eviction, error mapping) against hand-written
fakes standing in for pantograph.server.Server, never a real install.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.pantograph_sessions import (
    InteractiveCapacityError,
    InteractiveSessionCrashedError,
    InteractiveSessionNotFoundError,
    PantographSessionManager,
)

client = TestClient(app)


# --- Fakes standing in for the real pantograph package ---

class FakeTacticFailure(Exception):
    pass


class FakeServerError(Exception):
    pass


class FakeProc:
    def kill(self):
        pass


class FakeGoal:
    def __init__(self, text):
        self._text = text

    def __str__(self):
        return self._text


class FakeGoalState:
    def __init__(self, goals, is_solved=False):
        self.goals = [FakeGoal(g) for g in goals]
        self.is_solved = is_solved


class FakeSite:
    def __init__(self, goal_id=None):
        self.goal_id = goal_id


class FakeServer:
    """Stands in for pantograph.server.Server. `script` controls what
    goal_tactic does on each successive call: a GoalState to return, or an
    exception instance/class to raise."""

    def __init__(self, *args, **kwargs):
        self.proc = FakeProc()
        self._closed = False
        self.script = []

    def restart(self):
        pass

    def goal_start(self, statement):
        if statement == "__bad_statement__":
            raise ValueError("bad statement")
        return FakeGoalState(["⊢ True"])

    def goal_tactic(self, state, tactic, site):
        if not self.script:
            return FakeGoalState([], is_solved=True)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def _close(self):
        self._closed = True
        self.proc = None


def make_manager(max_sessions=2):
    settings.INTERACTIVE_MAX_SESSIONS = max_sessions
    mgr = PantographSessionManager()
    mgr.available = True
    mgr._server_cls = FakeServer
    mgr._Site = FakeSite
    mgr._TacticFailure = FakeTacticFailure
    mgr._ServerError = FakeServerError
    mgr._get_lean_path = lambda project_dir: None
    return mgr


# --- Unit tests against the manager directly ---

def test_start_and_apply_tactic_success():
    mgr = make_manager()
    started = mgr.start_session("forall (a b : Nat), a + b = b + a")
    assert started["goals"] == ["⊢ True"]
    assert started["is_solved"] is False

    session = mgr._sessions[started["session_id"]]
    session.server.script = [FakeGoalState(["⊢ a = a"])]
    result = mgr.apply_tactic(started["session_id"], "intro a b")
    assert result["status"] == "success"
    assert result["remaining_goals"] == ["⊢ a = a"]
    assert result["is_solved"] is False


def test_tactic_failure_keeps_session_alive():
    mgr = make_manager()
    started = mgr.start_session("forall (a b : Nat), a + b = b + a")
    session = mgr._sessions[started["session_id"]]
    session.server.script = [FakeTacticFailure("unknown identifier")]

    result = mgr.apply_tactic(started["session_id"], "bogus_tactic")
    assert result["status"] == "failed"
    assert "unknown identifier" in result["message"]
    # Session must still exist and state must be unchanged.
    assert started["session_id"] in mgr._sessions
    assert mgr._sessions[started["session_id"]].state.goals[0].__str__() == "⊢ True"


def test_server_error_with_dead_proc_evicts_session():
    mgr = make_manager()
    started = mgr.start_session("forall (a b : Nat), a + b = b + a")
    session = mgr._sessions[started["session_id"]]

    def die(*args, **kwargs):
        session.server.proc = None
        raise FakeServerError("process died")

    session.server.goal_tactic = die

    with pytest.raises(InteractiveSessionCrashedError):
        mgr.apply_tactic(started["session_id"], "intro a b")
    assert started["session_id"] not in mgr._sessions


def test_server_error_with_live_proc_is_a_normal_failure():
    mgr = make_manager()
    started = mgr.start_session("forall (a b : Nat), a + b = b + a")
    session = mgr._sessions[started["session_id"]]
    session.server.script = [FakeServerError("rejected")]

    result = mgr.apply_tactic(started["session_id"], "some_tactic")
    assert result["status"] == "failed"
    assert started["session_id"] in mgr._sessions


def test_max_sessions_enforced():
    mgr = make_manager(max_sessions=1)
    mgr.start_session("forall (a b : Nat), a + b = b + a")
    with pytest.raises(InteractiveCapacityError):
        mgr.start_session("forall (a b : Nat), a + b = b + a")


def test_bad_statement_raises_and_cleans_up():
    from app.services.pantograph_sessions import InteractiveStatementError

    mgr = make_manager()
    with pytest.raises(InteractiveStatementError):
        mgr.start_session("__bad_statement__")
    assert len(mgr._sessions) == 0


def test_idle_eviction():
    mgr = make_manager()
    started = mgr.start_session("forall (a b : Nat), a + b = b + a")
    session = mgr._sessions[started["session_id"]]
    session.last_used_at = time.time() - settings.INTERACTIVE_SESSION_IDLE_TIMEOUT_SECS - 1

    with mgr._lock:
        mgr._evict_idle_locked()
    assert started["session_id"] not in mgr._sessions
    assert session.server._closed is True


def test_close_unknown_session_returns_false():
    mgr = make_manager()
    assert mgr.close_session("does-not-exist") is False


def test_close_session_returns_true_and_cleans_up():
    mgr = make_manager()
    started = mgr.start_session("forall (a b : Nat), a + b = b + a")
    session = mgr._sessions[started["session_id"]]
    assert mgr.close_session(started["session_id"]) is True
    assert session.server._closed is True
    assert started["session_id"] not in mgr._sessions


def test_get_session_state_unknown_raises():
    mgr = make_manager()
    with pytest.raises(InteractiveSessionNotFoundError):
        mgr.get_session_state("does-not-exist")


def test_shutdown_closes_everything():
    mgr = make_manager(max_sessions=2)
    a = mgr.start_session("forall (a b : Nat), a + b = b + a")
    b = mgr.start_session("forall (a b : Nat), a + b = b + a")
    mgr.shutdown()
    assert len(mgr._sessions) == 0
    assert mgr._sessions.get(a["session_id"]) is None
    assert mgr._sessions.get(b["session_id"]) is None


# --- Route-wiring tests via TestClient, monkeypatching the app singleton ---

def test_routes_map_errors_to_status_codes(monkeypatch):
    mgr = make_manager()
    monkeypatch.setattr("app.main.pantograph_sessions", mgr)

    resp = client.post("/api/interactive/sessions", json={"statement": "forall (a b : Nat), a + b = b + a"})
    assert resp.status_code == 200
    sid = resp.json()["session_id"]

    resp = client.get(f"/api/interactive/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["goals"] == ["⊢ True"]

    resp = client.post(f"/api/interactive/sessions/{sid}/tactic", json={"tactic": "intro a b"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    resp = client.post("/api/interactive/sessions/does-not-exist/tactic", json={"tactic": "foo"})
    assert resp.status_code == 404

    resp = client.delete(f"/api/interactive/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["closed"] is True

    resp = client.delete(f"/api/interactive/sessions/{sid}")
    assert resp.status_code == 404


def test_capacity_error_maps_to_429(monkeypatch):
    mgr = make_manager(max_sessions=1)
    monkeypatch.setattr("app.main.pantograph_sessions", mgr)

    resp = client.post("/api/interactive/sessions", json={"statement": "forall (a b : Nat), a + b = b + a"})
    assert resp.status_code == 200

    resp = client.post("/api/interactive/sessions", json={"statement": "forall (a b : Nat), a + b = b + a"})
    assert resp.status_code == 429


def test_empty_statement_rejected():
    resp = client.post("/api/interactive/sessions", json={"statement": "   "})
    assert resp.status_code == 400


# --- Real unavailable-status test (no mocking) ---

def test_interactive_status_when_unavailable():
    # pantograph is genuinely not installed in this environment -- mirrors
    # the existing /api/harness unavailability precedent.
    resp = client.get("/api/interactive/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
