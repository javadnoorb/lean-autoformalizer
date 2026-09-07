import React, { useState } from 'react';
import { Target, CheckCircle2, AlertCircle, AlertTriangle, Terminal, Layers } from 'lucide-react';
import { LeanDiagnostic } from '../types';

interface InfoviewProps {
  goals: string[];
  diagnostics: LeanDiagnostic[];
  isValid: boolean | null;
  isProven?: boolean;
}

export const Infoview: React.FC<InfoviewProps> = ({
  goals,
  diagnostics,
  isValid,
  isProven,
}) => {
  const [activeTab, setActiveTab] = useState<'goals' | 'diagnostics'>('goals');

  const errors = diagnostics.filter((d) => d.severity === 'error');
  const warnings = diagnostics.filter((d) => d.severity === 'warning');

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-md flex flex-col h-[520px]">
      {/* Header with Tabs & Status Badge */}
      <div className="bg-slate-950 border-b border-slate-800 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center space-x-1">
          <button
            onClick={() => setActiveTab('goals')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
              activeTab === 'goals'
                ? 'bg-slate-800 text-slate-100 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Target className="w-3.5 h-3.5 text-blue-400" />
            <span>Tactic State</span>
            {goals.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-blue-500/20 text-blue-300 text-[10px]">
                {goals.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
              activeTab === 'diagnostics'
                ? 'bg-slate-800 text-slate-100 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Terminal className="w-3.5 h-3.5 text-amber-400" />
            <span>Messages</span>
            {diagnostics.length > 0 && (
              <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                errors.length > 0 ? 'bg-red-500/20 text-red-300' : 'bg-amber-500/20 text-amber-300'
              }`}>
                {diagnostics.length}
              </span>
            )}
          </button>
        </div>

        {/* Overall Status Pill */}
        <div>
          {isProven ? (
            <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-3 h-3" />
              <span>Proven</span>
            </span>
          ) : isValid === false ? (
            <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
              <AlertCircle className="w-3 h-3" />
              <span>Compile Error</span>
            </span>
          ) : isValid === true ? (
            <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Layers className="w-3 h-3" />
              <span>Typechecked</span>
            </span>
          ) : (
            <span className="text-xs text-slate-500 font-mono">Idle</span>
          )}
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 p-4 overflow-y-auto font-mono text-xs leading-relaxed space-y-3 bg-slate-950/50">
        {activeTab === 'goals' && (
          <div>
            {isProven ? (
              <div className="flex flex-col items-center justify-center py-16 text-center space-y-2 text-emerald-400">
                <CheckCircle2 className="w-12 h-12 stroke-1" />
                <h4 className="font-sans font-semibold text-sm text-emerald-300">No Goals Remaining</h4>
                <p className="font-sans text-xs text-slate-400 max-w-xs">
                  Theorem is formally verified and completely proved without <code>sorry</code>.
                </p>
              </div>
            ) : goals.length > 0 ? (
              <div className="space-y-3">
                <div className="text-[11px] font-sans font-medium text-slate-400 flex items-center justify-between border-b border-slate-800 pb-1.5">
                  <span>{goals.length} unsolved goal{goals.length > 1 ? 's' : ''}</span>
                  <span className="text-slate-500">Lean Infoview</span>
                </div>
                {goals.map((g, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-slate-900/90 border border-blue-500/20 rounded-lg text-slate-200 shadow-inner whitespace-pre-wrap selection:bg-blue-600"
                  >
                    {g}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-slate-500 text-center py-16 font-sans text-xs">
                No active goals to display. Click <strong>Autoformalize</strong> or <strong>Verify</strong> to inspect proof state.
              </div>
            )}
          </div>
        )}

        {activeTab === 'diagnostics' && (
          <div>
            {diagnostics.length === 0 ? (
              <div className="text-slate-500 text-center py-16 font-sans text-xs">
                No diagnostics or compiler messages reported.
              </div>
            ) : (
              <div className="space-y-2">
                {diagnostics.map((d, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-lg border text-xs leading-relaxed ${
                      d.severity === 'error'
                        ? 'bg-red-950/20 border-red-800/40 text-red-300'
                        : d.severity === 'warning'
                        ? 'bg-amber-950/20 border-amber-800/40 text-amber-300'
                        : 'bg-blue-950/20 border-blue-800/40 text-blue-300'
                    }`}
                  >
                    <div className="flex items-center space-x-1.5 font-sans font-semibold text-[11px] mb-1">
                      {d.severity === 'error' ? (
                        <AlertCircle className="w-3.5 h-3.5 text-red-400" />
                      ) : (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                      )}
                      <span className="uppercase tracking-wider">{d.severity}</span>
                      <span className="text-slate-500 font-mono font-normal">
                        Line {d.line}:{d.column}
                      </span>
                    </div>
                    <div className="font-mono whitespace-pre-wrap">{d.message}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
