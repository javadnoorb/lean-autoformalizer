import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { InputSection } from './components/InputSection';
import { LeanEditor } from './components/LeanEditor';
import { Infoview } from './components/Infoview';
import { ProofSteps } from './components/ProofSteps';
import { SettingsModal } from './components/SettingsModal';
import {
  getSystemStatus,
  getExamples,
  formalizeTheorem,
  proveTheorem,
  verifyLeanCode,
} from './api/client';
import { SystemStatus, TheoremExample, LeanDiagnostic, ProofStep } from './types';

export const App: React.FC = () => {
  // Application State
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [examples, setExamples] = useState<TheoremExample[]>([]);
  const [statement, setStatement] = useState('For any natural numbers a and b, (a + b)^2 = a^2 + 2*a*b + b^2');
  const [domainHint, setDomainHint] = useState('algebra');
  
  // Editor & Verification State
  const [leanCode, setLeanCode] = useState(
    'theorem add_sq_expand (a b : Nat) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2 := by\n  sorry'
  );
  const [explanation, setExplanation] = useState<string>(
    'Formalized as standard binomial expansion over natural numbers with Lean 4 exponentiation.'
  );
  const [diagnostics, setDiagnostics] = useState<LeanDiagnostic[]>([
    { severity: 'warning', line: 2, column: 3, message: "declaration uses 'sorry'" }
  ]);
  const [goals, setGoals] = useState<string[]>([
    '⊢ (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2'
  ]);
  const [isValid, setIsValid] = useState<boolean | null>(true);
  const [isProven, setIsProven] = useState<boolean>(false);

  // Prover execution state
  const [steps, setSteps] = useState<ProofStep[]>([]);
  const [winningTactic, setWinningTactic] = useState<string | undefined>();
  const [totalDurationMs, setTotalDurationMs] = useState<number | undefined>();

  // Feedback & Toast
  const [toast, setToast] = useState<string | null>(null);

  // Loading States
  const [isFormalizing, setIsFormalizing] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isProving, setIsProving] = useState(false);

  // Settings Modal State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [customApiKey, setCustomApiKey] = useState(() => localStorage.getItem('GEMINI_API_KEY') || '');
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem('GEMINI_MODEL') || 'gemini-2.5-flash');

  // Load initial metadata on mount
  useEffect(() => {
    getSystemStatus()
      .then(setStatus)
      .catch((err) => console.error('Status fetch error:', err));

    getExamples()
      .then(setExamples)
      .catch((err) => console.error('Examples fetch error:', err));
  }, []);

  const handleSaveApiKey = (key: string) => {
    setCustomApiKey(key);
    localStorage.setItem('GEMINI_API_KEY', key);
  };

  const handleSaveModel = (m: string) => {
    setSelectedModel(m);
    localStorage.setItem('GEMINI_MODEL', m);
  };

  // Handler: Select Example Preset
  const handleSelectExample = (ex: TheoremExample) => {
    setStatement(ex.english);
    if (ex.category) {
      setDomainHint(ex.category.toLowerCase().replace(' ', '_'));
    }
  };

  // Handler: Autoformalize
  const handleFormalize = async () => {
    if (!statement.trim()) return;
    setIsFormalizing(true);
    setSteps([]);
    setWinningTactic(undefined);
    setIsProven(false);

    try {
      const res = await formalizeTheorem(statement, domainHint, customApiKey, selectedModel);
      setLeanCode(res.lean_code);
      setExplanation(res.explanation);
      setIsValid(res.is_valid);
      setDiagnostics(res.diagnostics);
      setGoals(res.goals);
      setToast('✨ Lean 4 theorem formalized successfully!');
      setTimeout(() => setToast(null), 4000);
    } catch (err: any) {
      alert(err.message || 'Autoformalization request failed.');
    } finally {
      setIsFormalizing(false);
    }
  };

  // Handler: Verify Code in Editor
  const handleVerify = async () => {
    if (!leanCode.trim()) return;
    setIsVerifying(true);
    try {
      const res = await verifyLeanCode(leanCode);
      setIsValid(res.is_valid);
      setDiagnostics(res.diagnostics);
      setGoals(res.goals);
      if (res.is_valid && !res.has_sorry && res.goals.length === 0) {
        setIsProven(true);
      } else {
        setIsProven(false);
      }
      setToast('Verification complete.');
      setTimeout(() => setToast(null), 3000);
    } catch (err: any) {
      console.error(err);
    } finally {
      setIsVerifying(false);
    }
  };

  // Handler: Auto-Prove Theorem
  const handleProve = async (strategy: string) => {
    if (!leanCode.trim()) return;
    setIsProving(true);
    setSteps([]);
    setWinningTactic(undefined);

    try {
      const res = await proveTheorem(leanCode, strategy, customApiKey, selectedModel);
      setLeanCode(res.proof_code);
      setSteps(res.steps);
      setWinningTactic(res.winning_tactic);
      setTotalDurationMs(res.total_duration_ms);
      setDiagnostics(res.diagnostics);
      setGoals(res.remaining_goals);

      if (res.success) {
        setIsProven(true);
        setIsValid(true);
        setToast('🎉 Theorem successfully proven!');
      } else {
        setIsProven(false);
        setToast('Proof search completed. Unsolved goals remain.');
      }
      setTimeout(() => setToast(null), 4000);
    } catch (err: any) {
      alert(err.message || 'Proof search request failed.');
    } finally {
      setIsProving(false);
    }
  };

  const isOffline = !customApiKey && !status?.gemini_key_configured;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header
        status={status}
        onOpenSettings={() => setIsSettingsOpen(true)}
        hasCustomKey={Boolean(customApiKey)}
      />

      {/* Floating Toast Notification */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 bg-slate-900 border border-blue-500/40 text-blue-200 px-4 py-2.5 rounded-lg shadow-xl text-xs font-medium flex items-center space-x-2 animate-in fade-in slide-in-from-bottom-2">
          <span>{toast}</span>
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Offline Mode Banner */}
        {isOffline && (
          <div className="p-3 bg-amber-950/30 border border-amber-500/30 rounded-xl flex items-center justify-between text-xs text-amber-200">
            <div className="flex items-center space-x-2">
              <span className="text-amber-400 font-bold">Offline / Heuristic Mode:</span>
              <span>
                Algebraic equations and presets are autoformalized locally. For full AI reasoning on arbitrary English statements, connect your Gemini API Key.
              </span>
            </div>
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="px-3 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-md font-semibold text-xs transition shrink-0 ml-3"
            >
              Add Gemini API Key
            </button>
          </div>
        )}

        {/* Step 1: Input & Presets */}
        <InputSection
          statement={statement}
          setStatement={setStatement}
          domainHint={domainHint}
          setDomainHint={setDomainHint}
          examples={examples}
          onSelectExample={handleSelectExample}
          onFormalize={handleFormalize}
          isLoading={isFormalizing}
        />

        {/* Step 2: Main Interactive Grid (Editor + Infoview) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7">
            <LeanEditor
              code={leanCode}
              onChange={setLeanCode}
              onVerify={handleVerify}
              onProve={handleProve}
              isVerifying={isVerifying}
              isProving={isProving}
              explanation={explanation}
            />
          </div>

          <div className="lg:col-span-5">
            <Infoview
              goals={goals}
              diagnostics={diagnostics}
              isValid={isValid}
              isProven={isProven}
            />
          </div>
        </div>

        {/* Step 3: Execution Trace when Proving */}
        <ProofSteps
          steps={steps}
          winningTactic={winningTactic}
          totalDurationMs={totalDurationMs}
          success={isProven}
        />
      </main>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        status={status}
        customApiKey={customApiKey}
        onSaveApiKey={handleSaveApiKey}
        selectedModel={selectedModel}
        onSaveModel={handleSaveModel}
      />
    </div>
  );
};
export default App;
