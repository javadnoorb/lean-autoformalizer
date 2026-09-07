"""Prompts and tactic lists for Lean 4 automated theorem proving."""

# Standard fast hammer tactics to evaluate first
FAST_HAMMER_TACTICS = [
    ("rfl", "Reflexivity (definitionally equal)"),
    ("omega", "Presburger arithmetic decision procedure (integer/natural linear arithmetic)"),
    ("decide", "Decidable proposition evaluator"),
    ("simp", "Lean 4 standard simplifier"),
    ("aesop", "Automated extensible search for obvious proofs"),
    ("intro; rfl", "Introduction followed by reflexivity"),
    ("intro; simp", "Introduction followed by simplifier"),
    ("intro; omega", "Introduction followed by arithmetic solver"),
    ("intro h; exact h", "Direct hypothesis assumption"),
    ("intro h; cases h; rfl", "Case analysis on hypothesis"),
    ("intro h; cases h with | intro k hk => exists (2 * k ^ 2); omega", "Existential witness construction")
]

PROOF_SEARCH_SYSTEM_PROMPT = """You are an automated Lean 4 theorem prover assistant.
Given a Lean 4 theorem statement and the compiler's diagnostic/goal output, your task is to supply a valid proof script that closes all goals without using `sorry`.

RULES:
1. Output ONLY valid Lean 4 tactics inside a `by` block or replace the `:= by sorry` with your proof.
2. Use concise, reliable tactics like `omega`, `rfl`, `simp`, `intro`, `cases`, `rcases`, `linarith`, `ring`, `aesop`.
3. Do NOT use `sorry` in the solution.
4. Return strictly a JSON object:
{
  "tactic_script": "<tactic commands to put inside 'by ...'>",
  "full_code": "<complete theorem code with proof replacing sorry>",
  "explanation": "<brief reasoning for the proof steps>"
}
"""

def build_proof_prompt(lean_code: str, diagnostics: list = None, goals: list = None) -> str:
    diag_str = "\n".join([f"- Line {d.get('line', 1)}: {d.get('message', '')}" for d in (diagnostics or [])])
    goals_str = "\n".join([f"- Goal: {g}" for g in (goals or [])])
    
    extra = ""
    if diag_str:
        extra += f"\nCompiler Diagnostics:\n{diag_str}"
    if goals_str:
        extra += f"\nUnsolved Goals:\n{goals_str}"
        
    return f"""Please find a complete Lean 4 proof for this theorem:

```lean
{lean_code}
```
{extra}

Provide the complete proof without using `sorry`. Return strictly the requested JSON.
"""
