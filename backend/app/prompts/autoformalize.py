"""Prompt templates and few-shot examples for autoformalizing English math statements into Lean 4."""

AUTOFORMALIZE_SYSTEM_PROMPT = """You are an expert mathematician and Lean 4 formalization assistant.
Your job is to translate informal mathematical theorems stated in plain English (and/or LaTeX) into valid, idiomatic Lean 4 code.

RULES FOR LEAN 4 FORMALIZATION:
1. Use Lean 4 syntax, NOT Lean 3 (e.g. `Nat`, not `nat`; `Int`, not `int`; `Prop`, not `Type`; `theorem name (...) : (...) := by sorry`).
2. Keep dependencies self-contained and small by default (use standard library / prelude types `Nat`, `Int`, `List`, `Bool`, basic logical connectives `∧`, `∨`, `¬`, `→`, `↔`, `∀`, `∃` unless Mathlib is explicitly requested).
3. If helper definitions are needed (e.g. `def IsEven (n : Nat) : Prop := ∃ k, n = 2 * k`), include them right above the theorem.
4. Always end the theorem with `:= by sorry` so it typechecks and leaves the goal open for automated proving.
5. Choose a clear, snake_case theorem name reflecting the mathematical statement (e.g. `sum_consecutive_integers`, `even_square_even`).
6. Give a concise 1-3 sentence explanation of the typing choices and mathematical formulation.

OUTPUT FORMAT:
Return strictly a JSON object with this schema:
{
  "theorem_name": "<identifier>",
  "lean_code": "<complete valid Lean 4 code containing the theorem and any required defs, ending with := by sorry>",
  "explanation": "<brief explanation of formalization>"
}
"""

FEW_SHOT_EXAMPLES = [
    {
        "english": "For all natural numbers n, n + 0 = n",
        "json": {
            "theorem_name": "nat_add_zero_id",
            "lean_code": "theorem nat_add_zero_id (n : Nat) : n + 0 = n := by\n  sorry",
            "explanation": "Formalized as an identity on the standard Lean 4 `Nat` type with universal quantification."
        }
    },
    {
        "english": "For any natural numbers a and b, (a + b)^2 = a^2 + 2*a*b + b^2",
        "json": {
            "theorem_name": "add_sq_expand",
            "lean_code": "theorem add_sq_expand (a b : Nat) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2 := by\n  sorry",
            "explanation": "Standard binomial square identity on natural numbers using Lean 4 exponentiation and arithmetic."
        }
    },
    {
        "english": "If a natural number n is even, then n squared is also even.",
        "json": {
            "theorem_name": "even_sq_even",
            "lean_code": "def IsEven (n : Nat) : Prop := ∃ k : Nat, n = 2 * k\n\ntheorem even_sq_even (n : Nat) (h : IsEven n) : IsEven (n ^ 2) := by\n  sorry",
            "explanation": "Defined `IsEven` predicate using existential quantification, then stated the implication as a hypothesis `(h : IsEven n)`."
        }
    },
    {
        "english": "For all propositions P and Q, if P and Q holds, then Q and P holds.",
        "json": {
            "theorem_name": "and_comm_prop",
            "lean_code": "theorem and_comm_prop (P Q : Prop) : P ∧ Q → Q ∧ P := by\n  sorry",
            "explanation": "Formalized as a propositional logic implication between conjunctions."
        }
    }
]

def build_autoformalize_prompt(statement: str, domain_hint: str = None) -> str:
    domain_part = f"\nDomain / Context hint: {domain_hint}" if domain_hint else ""
    return f"""Please formalize the following mathematical statement into Lean 4:

Statement:
{statement}{domain_part}

Remember to return only the JSON object with keys 'theorem_name', 'lean_code', and 'explanation'.
"""
