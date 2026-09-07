"""LeanDojo integration harness for programmatic Lean 4 interaction."""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class LeanDojoHarness:
    def __init__(self):
        self.is_available = False
        self._check_availability()

    def _check_availability(self):
        try:
            import lean_dojo
            self.is_available = True
            logger.info("LeanDojo is successfully imported.")
        except ImportError:
            self.is_available = False
            logger.info("LeanDojo is not currently installed or not available in the current Python environment.")

    def get_status(self) -> Dict[str, Any]:
        return {
            "available": self.is_available,
            "description": "LeanDojo harness for interactive tactic exploration and proof tree extraction." if self.is_available else "LeanDojo package not installed in current Python environment."
        }

    def run_interactive_tactic(self, repo_url: str, commit: str, file_path: str, theorem_name: str, tactic: str) -> Dict[str, Any]:
        """Execute a single tactic in a LeanDojo environment if available."""
        if not self.is_available:
            return {
                "success": False,
                "error": "LeanDojo is not available."
            }

        try:
            from lean_dojo import LeanGitRepo, Theorem, Dojo
            repo = LeanGitRepo(repo_url, commit)
            thm = Theorem(repo, file_path, theorem_name)
            with Dojo(thm) as (dojo, init_state):
                res = dojo.run_tac(init_state, tactic)
                return {
                    "success": True,
                    "initial_state": str(init_state),
                    "result_state": str(res)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

leandojo_harness = LeanDojoHarness()
