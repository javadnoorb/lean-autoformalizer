export interface LeanDiagnostic {
  severity: 'error' | 'warning' | 'info';
  line: number;
  column: number;
  message: string;
}

export interface FormalizeResponse {
  lean_code: string;
  theorem_name: string;
  explanation: string;
  is_valid: boolean;
  diagnostics: LeanDiagnostic[];
  goals: string[];
}

export interface ProofStep {
  tactic: string;
  status: 'success' | 'failed' | 'partial';
  message?: string;
  remaining_goals: string[];
  duration_ms: number;
}

export interface ProveResponse {
  success: boolean;
  proof_code: string;
  winning_tactic?: string;
  steps: ProofStep[];
  diagnostics: LeanDiagnostic[];
  remaining_goals: string[];
  total_duration_ms: number;
}

export interface VerifyResponse {
  is_valid: boolean;
  has_sorry: boolean;
  diagnostics: LeanDiagnostic[];
  goals: string[];
}

export interface SystemStatus {
  status: string;
  lean_installed: boolean;
  lean_version?: string;
  gemini_key_configured: boolean;
  model: string;
}

export interface TheoremExample {
  title: string;
  category: string;
  english: string;
  hint: string;
}
