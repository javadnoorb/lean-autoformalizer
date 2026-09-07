import React from 'react';
import { CheckCircle2, XCircle, Clock, Zap, Cpu } from 'lucide-react';
import { ProofStep } from '../types';

interface ProofStepsProps {
  steps: ProofStep[];
  winningTactic?: string;
  totalDurationMs?: number;
  success?: boolean;
}

export const ProofSteps: React.FC<ProofStepsProps> = ({
  steps,
  winningTactic,
  totalDurationMs,
  success,
}) => {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
        <div className="flex items-center space-x-2">
          <Cpu className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
            Automated Prover Execution Trace
          </h3>
        </div>
        {totalDurationMs !== undefined && (
          <div className="flex items-center space-x-1 text-slate-400 text-xs font-mono">
            <Clock className="w-3.5 h-3.5" />
            <span>{totalDurationMs} ms</span>
          </div>
        )}
      </div>

      {/* Winning tactic highlight banner */}
      {success && winningTactic && (
        <div className="p-3 bg-emerald-950/30 border border-emerald-500/30 rounded-lg flex items-center space-x-2 text-xs text-emerald-300">
          <Zap className="w-4 h-4 text-emerald-400 fill-emerald-400 shrink-0" />
          <span>
            Successfully solved using tactic:{' '}
            <strong className="font-mono text-emerald-200">{winningTactic}</strong>
          </span>
        </div>
      )}

      {/* List of tactic steps */}
      <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
        {steps.map((step, idx) => (
          <div
            key={idx}
            className={`p-2.5 rounded-lg border text-xs flex items-center justify-between ${
              step.status === 'success'
                ? 'bg-emerald-950/20 border-emerald-700/40 text-emerald-200'
                : 'bg-slate-950/40 border-slate-800/80 text-slate-400'
            }`}
          >
            <div className="flex items-center space-x-2 truncate mr-2">
              {step.status === 'success' ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              ) : (
                <XCircle className="w-3.5 h-3.5 text-slate-600 shrink-0" />
              )}
              <code className="px-1.5 py-0.5 rounded bg-slate-900 text-slate-200 font-mono text-[11px] border border-slate-800">
                {step.tactic}
              </code>
              <span className="text-[11px] truncate text-slate-400">{step.message}</span>
            </div>

            <span className="font-mono text-[10px] text-slate-500 shrink-0">
              {step.duration_ms} ms
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
