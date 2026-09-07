import re
import time
from typing import List, Optional
from app.config import settings
from app.models.schemas import ProveRequest, ProveResponse, ProofStep, LeanDiagnostic
from app.prompts.proof_search import FAST_HAMMER_TACTICS, build_proof_prompt, PROOF_SEARCH_SYSTEM_PROMPT
from app.services.lean_runner import lean_runner

class ProverService:
    def __init__(self):
        pass

    def _replace_sorry_with_tactic(self, code: str, tactic: str) -> str:
        """Replace the `:= by sorry` or `by sorry` with the supplied tactic."""
        # Pattern 1: := by\n  sorry
        pattern1 = r":=\s*by\s*(?:\n\s*)?sorry"
        if re.search(pattern1, code):
            return re.sub(pattern1, f":= by\n  {tactic}", code, count=1)
        
        # Pattern 2: by sorry
        pattern2 = r"\bby\s+sorry\b"
        if re.search(pattern2, code):
            return re.sub(pattern2, f"by {tactic}", code, count=1)

        # Fallback: append or replace sorry
        if "sorry" in code:
            return code.replace("sorry", tactic, 1)

        return code

    def prove(self, req: ProveRequest) -> ProveResponse:
        start_time = time.time()
        steps: List[ProofStep] = []
        original_code = req.lean_code

        # First verify the input theorem statement
        init_valid, init_diags, init_goals = lean_runner.run_lean_code(original_code)
        if not init_valid:
            # Code has compile errors before we even try proving
            return ProveResponse(
                success=False,
                proof_code=original_code,
                steps=[ProofStep(
                    tactic="initial_check",
                    status="failed",
                    message="Theorem signature or definitions have compilation errors.",
                    remaining_goals=init_goals,
                    duration_ms=int((time.time() - start_time) * 1000)
                )],
                diagnostics=init_diags,
                remaining_goals=init_goals,
                total_duration_ms=int((time.time() - start_time) * 1000)
            )

        # Stage 1: Fast Hammer Tactics
        for tactic_str, tactic_desc in FAST_HAMMER_TACTICS:
            t_start = time.time()
            candidate_code = self._replace_sorry_with_tactic(original_code, tactic_str)
            is_valid, diags, goals = lean_runner.run_lean_code(candidate_code)
            t_elapsed = int((time.time() - t_start) * 1000)

            # A proof is successful if it compiles with zero errors, zero sorry, and zero open goals
            has_error = any(d.severity == "error" for d in diags)
            has_sorry = any("sorry" in d.message for d in diags) or ("sorry" in candidate_code)
            has_open_goals = len(goals) > 0

            if is_valid and not has_error and not has_sorry and not has_open_goals:
                steps.append(ProofStep(
                    tactic=tactic_str,
                    status="success",
                    message=f"Solved with {tactic_desc}",
                    remaining_goals=[],
                    duration_ms=t_elapsed
                ))
                return ProveResponse(
                    success=True,
                    proof_code=candidate_code,
                    winning_tactic=tactic_str,
                    steps=steps,
                    diagnostics=diags,
                    remaining_goals=[],
                    total_duration_ms=int((time.time() - start_time) * 1000)
                )
            else:
                steps.append(ProofStep(
                    tactic=tactic_str,
                    status="failed",
                    message=f"Failed to close goals: {diags[0].message if diags else 'Unsolved goals'}",
                    remaining_goals=goals,
                    duration_ms=t_elapsed
                ))

        # Stage 2: If strategy includes LLM or hammer failed, try LLM guided proof
        if req.strategy in ("llm_refinement", "hybrid"):
            llm_step, llm_response = self._try_llm_proof(req, original_code, steps, start_time)
            if llm_response is not None:
                return llm_response

        # If all tactics failed
        return ProveResponse(
            success=False,
            proof_code=original_code,
            steps=steps,
            diagnostics=init_diags,
            remaining_goals=init_goals,
            total_duration_ms=int((time.time() - start_time) * 1000)
        )

    def _try_llm_proof(self, req: ProveRequest, original_code: str, steps: list, start_time: float) -> tuple:
        """Attempt LLM proof synthesis when hammer tactics cannot close goals."""
        key = req.api_key or settings.GEMINI_API_KEY
        if not key:
            return None, None

        try:
            from google import genai
            client = genai.Client(api_key=key)
            prompt = build_proof_prompt(original_code)

            t_start = time.time()
            response = client.models.generate_content(
                model=req.model or settings.GEMINI_MODEL,
                contents=[
                    {"role": "user", "parts": [{"text": PROOF_SEARCH_SYSTEM_PROMPT}]},
                    {"role": "user", "parts": [{"text": prompt}]}
                ],
                config={"response_mime_type": "application/json", "temperature": 0.2}
            )

            import json
            parsed = json.loads(response.text or "{}")
            tactic_script = parsed.get("tactic_script", "")
            full_code = parsed.get("full_code", "")

            candidate = full_code if full_code and "theorem" in full_code else self._replace_sorry_with_tactic(original_code, tactic_script)
            is_valid, diags, goals = lean_runner.run_lean_code(candidate)
            t_elapsed = int((time.time() - t_start) * 1000)

            has_error = any(d.severity == "error" for d in diags)
            has_sorry = any("sorry" in d.message for d in diags) or ("sorry" in candidate)

            if is_valid and not has_error and not has_sorry and not goals:
                steps.append(ProofStep(
                    tactic=tactic_script or "llm_generated_proof",
                    status="success",
                    message="Solved by LLM reasoning agent",
                    remaining_goals=[],
                    duration_ms=t_elapsed
                ))
                return None, ProveResponse(
                    success=True,
                    proof_code=candidate,
                    winning_tactic="llm_agent",
                    steps=steps,
                    diagnostics=diags,
                    remaining_goals=[],
                    total_duration_ms=int((time.time() - start_time) * 1000)
                )
            else:
                steps.append(ProofStep(
                    tactic=tactic_script or "llm_generated_proof",
                    status="failed",
                    message="LLM candidate did not completely close goals.",
                    remaining_goals=goals,
                    duration_ms=t_elapsed
                ))
        except Exception as e:
            steps.append(ProofStep(
                tactic="llm_agent",
                status="failed",
                message=f"LLM request error: {str(e)}",
                remaining_goals=[],
                duration_ms=0
            ))

        return None, None

prover = ProverService()
