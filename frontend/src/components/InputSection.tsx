import React from 'react';
import { Sparkles, BookOpen, ArrowRight, Loader2 } from 'lucide-react';
import { TheoremExample } from '../types';

interface InputSectionProps {
  statement: string;
  setStatement: (val: string) => void;
  examples: TheoremExample[];
  onSelectExample: (ex: TheoremExample) => void;
  onFormalize: () => void;
  isLoading: boolean;
  autoProve: boolean;
  setAutoProve: (val: boolean) => void;
}

export const InputSection: React.FC<InputSectionProps> = ({
  statement,
  setStatement,
  examples,
  onSelectExample,
  onFormalize,
  isLoading,
  autoProve,
  setAutoProve,
}) => {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
      {/* Top row: Label & Examples */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2">
          <BookOpen className="w-4 h-4 text-blue-400" />
          <label className="text-sm font-medium text-slate-200">
            Theorem in Plain English / Informal Math
          </label>
        </div>

        {/* Quick Example Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 text-xs">
          <span className="text-slate-500 font-medium mr-1">Presets:</span>
          {examples.slice(0, 4).map((ex) => (
            <button
              key={ex.hint}
              onClick={() => onSelectExample(ex)}
              className="px-2.5 py-1 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition truncate max-w-[140px]"
              title={ex.english}
            >
              {ex.title}
            </button>
          ))}
        </div>
      </div>

      {/* Input Textarea */}
      <div className="relative">
        <textarea
          rows={3}
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              onFormalize();
            }
          }}
          placeholder="e.g. For any natural numbers a and b, (a + b)^2 = a^2 + 2*a*b + b^2..."
          className="w-full bg-slate-950/80 border border-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-lg p-3.5 text-slate-100 placeholder-slate-500 text-sm font-normal resize-y min-h-[90px] outline-none transition"
        />
        <div className="absolute right-2.5 bottom-2.5 text-[11px] text-slate-500">
          Press <kbd className="px-1 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px]">Ctrl+Enter</kbd> to formalize
        </div>
      </div>

      {/* Bottom controls: Formalize Action */}
      <div className="flex items-center justify-end gap-4 pt-1">
        {/* Auto-Prove Toggle */}
        <label
          className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer select-none"
          title="After formalizing, immediately try to close the goal with fast deterministic tactics (omega/rfl/simp/aesop) instead of leaving `:= by sorry`. Off by default, and resets each session -- doesn't silently persist as a hidden behavior change."
        >
          <input
            type="checkbox"
            checked={autoProve}
            onChange={(e) => setAutoProve(e.target.checked)}
            className="w-3.5 h-3.5 rounded border-slate-700 bg-slate-900 text-blue-500 focus:ring-blue-500 focus:ring-offset-0 cursor-pointer"
          />
          <span>Auto-prove</span>
        </label>

        {/* Action Button */}
        <button
          onClick={onFormalize}
          disabled={isLoading || !statement.trim()}
          className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium text-sm transition shadow-md shadow-blue-600/20 cursor-pointer disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Formalizing...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4 text-blue-200" />
              <span>Autoformalize into Lean 4</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </>
          )}
        </button>
      </div>
    </div>
  );
};
