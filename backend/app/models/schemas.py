from typing import List, Optional
from pydantic import BaseModel, Field

class LeanDiagnostic(BaseModel):
    severity: str = Field(..., description="error, warning, or info")
    line: int = Field(default=1, description="1-indexed line number")
    column: int = Field(default=1, description="1-indexed column number")
    message: str = Field(..., description="Compiler diagnostic message")

class FormalizeRequest(BaseModel):
    english_statement: str = Field(..., description="Theorem in natural English")
    theorem_name: Optional[str] = Field(default=None, description="Optional custom identifier for theorem")
    domain_hint: Optional[str] = Field(default=None, description="e.g. 'algebra', 'number_theory', 'logic'")
    api_key: Optional[str] = Field(default=None, description="Optional per-request Gemini API key")
    model: Optional[str] = Field(default=None, description="Gemini model name")

class FormalizeResponse(BaseModel):
    lean_code: str = Field(..., description="Generated Lean 4 code with signature and sorry proof")
    theorem_name: str = Field(..., description="Extracted or generated theorem identifier")
    explanation: str = Field(..., description="Brief explanation of the formalization choices")
    is_valid: bool = Field(..., description="Whether the theorem signature typechecked successfully in Lean")
    diagnostics: List[LeanDiagnostic] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list, description="Extracted tactic goals at the sorry position")

class ProofStep(BaseModel):
    tactic: str
    status: str  # 'success', 'failed', 'partial'
    message: Optional[str] = None
    remaining_goals: List[str] = Field(default_factory=list)
    duration_ms: int = 0

class ProveRequest(BaseModel):
    lean_code: str = Field(..., description="Lean 4 code with theorem and proof (or sorry)")
    theorem_name: Optional[str] = Field(default=None)
    strategy: str = Field(default="fast_hammer", description="'fast_hammer', 'tactics_search', or 'llm_refinement'")
    timeout_seconds: int = Field(default=10)
    api_key: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)

class ProveResponse(BaseModel):
    success: bool = Field(..., description="True if proven without sorry and without errors")
    proof_code: str = Field(..., description="Full resulting Lean 4 code")
    winning_tactic: Optional[str] = Field(default=None, description="Tactic that successfully proved the theorem")
    steps: List[ProofStep] = Field(default_factory=list)
    diagnostics: List[LeanDiagnostic] = Field(default_factory=list)
    remaining_goals: List[str] = Field(default_factory=list)
    total_duration_ms: int = 0

class VerifyRequest(BaseModel):
    lean_code: str = Field(..., description="Arbitrary Lean 4 code snippet to verify")

class VerifyResponse(BaseModel):
    is_valid: bool = Field(..., description="True if no compiler errors")
    has_sorry: bool = Field(..., description="True if the proof contains sorry or unsolved goals")
    diagnostics: List[LeanDiagnostic] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)

class SystemStatusResponse(BaseModel):
    status: str
    lean_installed: bool
    lean_version: Optional[str] = None
    wsl_enabled: bool
    distro: str
    gemini_key_configured: bool
    model: str
