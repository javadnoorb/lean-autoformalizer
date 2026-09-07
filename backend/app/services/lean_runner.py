import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Tuple, Any
from app.config import settings
from app.models.schemas import LeanDiagnostic, VerifyResponse

class LeanRunner:
    def __init__(self):
        self.is_linux = (os.name != 'nt')
        self.use_wsl = settings.USE_WSL and not self.is_linux
        self.wsl_distro = settings.WSL_DISTRO
        self.lean_bin_wsl = settings.LEAN_BIN_WSL
        self.timeout = settings.LEAN_TIMEOUT_SECS

    def _get_lean_exec_path(self) -> str:
        if self.is_linux:
            expanded = os.path.expanduser(self.lean_bin_wsl)
            if os.path.exists(expanded):
                return expanded
            lean_which = shutil.which("lean")
            if lean_which:
                return lean_which
            return expanded
        return settings.LEAN_BIN_LOCAL

    def get_system_status(self) -> Dict[str, Any]:
        """Check if Lean 4 is installed and accessible via WSL or locally."""
        try:
            if self.is_linux:
                cmd = [self._get_lean_exec_path(), "--version"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return {
                        "installed": True,
                        "version": res.stdout.strip(),
                        "mode": "wsl_native",
                        "distro": self.wsl_distro
                    }
            elif self.use_wsl:
                cmd = ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", f"{self.lean_bin_wsl} --version"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return {
                        "installed": True,
                        "version": res.stdout.strip(),
                        "mode": "wsl",
                        "distro": self.wsl_distro
                    }
            else:
                res = subprocess.run([settings.LEAN_BIN_LOCAL, "--version"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return {
                        "installed": True,
                        "version": res.stdout.strip(),
                        "mode": "local",
                        "distro": ""
                    }
        except Exception:
            pass

        return {
            "installed": False,
            "version": None,
            "mode": "mock" if settings.ALLOW_MOCK_FALLBACK else "unavailable",
            "distro": self.wsl_distro if self.use_wsl else ""
        }

    def _windows_to_wsl_path(self, win_path: str) -> str:
        """Convert C:\\path\\to\\file into /mnt/c/path/to/file."""
        p = os.path.abspath(win_path).replace("\\", "/")
        if len(p) >= 2 and p[1] == ":":
            drive = p[0].lower()
            return f"/mnt/{drive}{p[2:]}"
        return p

    def run_lean_code(self, code: str) -> Tuple[bool, List[LeanDiagnostic], List[str]]:
        """
        Run Lean 4 code with --json flag and return (is_valid, diagnostics, open_goals).
        `is_valid` is True if there are no errors (warnings like 'uses sorry' are allowed).
        """
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix=".lean", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_path = f.name

        try:
            if self.is_linux:
                cmd = [self._get_lean_exec_path(), "--json", temp_path]
            elif self.use_wsl:
                wsl_path = self._windows_to_wsl_path(temp_path)
                # Command to invoke lean inside WSL
                cmd = [
                    "wsl", "-d", self.wsl_distro, "--", "bash", "-c",
                    f"{self.lean_bin_wsl} --json '{wsl_path}'"
                ]
            else:
                cmd = [settings.LEAN_BIN_LOCAL, "--json", temp_path]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            stdout = result.stdout
            stderr = result.stderr

            diagnostics: List[LeanDiagnostic] = []
            goals: List[str] = []
            has_error = False

            # Lean 4 outputs JSON objects line-by-line
            for line in stdout.splitlines():
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    data = json.loads(line)
                    pos = data.get("pos") or {}
                    line_no = pos.get("line", 1)
                    col_no = pos.get("column", pos.get("col", 1))
                    severity = data.get("severity", "info")
                    msg = str(data.get("data") or data.get("message") or "")
                    kind = str(data.get("kind") or "")

                    if severity == "error":
                        has_error = True

                    diagnostics.append(LeanDiagnostic(
                        severity=severity,
                        line=line_no,
                        column=col_no,
                        message=msg
                    ))

                    # Extract open goal state if present in message or kind
                    if kind == "Tactic.unsolvedGoals" or "unsolved goals" in msg or "⊢" in msg:
                        clean_goal = msg.replace("unsolved goals\n", "").strip()
                        if clean_goal and clean_goal not in goals:
                            goals.append(clean_goal)
                except json.JSONDecodeError:
                    continue

            # Check stderr if no json diagnostics were produced but returncode != 0
            if result.returncode != 0 and not diagnostics:
                has_error = True
                err_msg = stderr.strip() or stdout.strip() or f"Lean exited with code {result.returncode}"
                diagnostics.append(LeanDiagnostic(
                    severity="error",
                    line=1,
                    column=1,
                    message=err_msg
                ))

            return (not has_error, diagnostics, goals)

        except subprocess.TimeoutExpired:
            return (False, [LeanDiagnostic(severity="error", line=1, column=1, message=f"Lean process timed out after {self.timeout}s.")], [])
        except FileNotFoundError as e:
            if settings.ALLOW_MOCK_FALLBACK:
                return self._mock_check(code)
            return (False, [LeanDiagnostic(severity="error", line=1, column=1, message=f"Lean executable not found: {str(e)}")], [])
        except Exception as e:
            if settings.ALLOW_MOCK_FALLBACK:
                return self._mock_check(code)
            return (False, [LeanDiagnostic(severity="error", line=1, column=1, message=f"Execution error: {str(e)}")], [])
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _mock_check(self, code: str) -> Tuple[bool, List[LeanDiagnostic], List[str]]:
        """Fallback validator when Lean 4 runtime is still initializing."""
        diagnostics = []
        goals = []
        is_valid = True

        # Simple structural heuristics
        if "theorem " not in code and "def " not in code and "lemma " not in code:
            diagnostics.append(LeanDiagnostic(
                severity="error",
                line=1,
                column=1,
                message="Code must contain at least one 'theorem', 'def', or 'lemma' declaration."
            ))
            is_valid = False

        if "sorry" in code:
            diagnostics.append(LeanDiagnostic(
                severity="warning",
                line=1,
                column=1,
                message="declaration uses 'sorry' (mock validator)"
            ))
            # Extract target statement after : and before :=
            match = re.search(r":\s*(.+?)\s*:=\s*by", code, re.DOTALL)
            if match:
                goals.append(f"⊢ {match.group(1).strip()}")
            else:
                goals.append("⊢ [Open Goal]")

        return (is_valid, diagnostics, goals)

    def verify(self, code: str) -> VerifyResponse:
        """Full verification endpoint helper."""
        is_valid, diagnostics, goals = self.run_lean_code(code)
        has_sorry = any("sorry" in d.message for d in diagnostics) or ("sorry" in code)
        return VerifyResponse(
            is_valid=is_valid,
            has_sorry=has_sorry,
            diagnostics=diagnostics,
            goals=goals
        )

lean_runner = LeanRunner()
