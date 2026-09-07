import React from 'react';
import { Sparkles, BookOpen, ArrowRight, Loader2 } from 'lucide-react';
import { TheoremExample } from '../types';

interface InputSectionProps {
  statement: string;
  setStatement: (val: string) => void;
  domainHint: string;
  setDomainHint: (val: string) => void;
  examples: TheoremExample[];
  onSelectExample: (ex: TheoremExample) => void;
  onFormalize: () => void;
  isLoading: boolean;
}

export const InputSection: React.FC<InputSectionProps> = ({
  statement,
  setStatement,
  domainHint,
  setDomainHint,
  examples,
  onSelectExample,
  onFormalize,
  isLoading,
}) => {
  const domains = [
    { id: 'arithmetic', label: 'Arithmetic' },
    { id: 'algebra', label: 'Algebra' },
    { id: 'logic', label: 'Logic' },
    { id: 'number_theory', label: 'Number Theory' },
  ];

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

      {/* Bottom controls: Domain selector & Formalize Action */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        {/* Domain Hint Pills */}
        <div className="flex items-center space-x-1.5 text-xs">
          <span className="text-slate-500 mr-1">Domain:</span>
          {domains.map((d) => (
            <button
              key={d.id}
              onClick={() => setDomainHint(domainHint === d.id ? '' : d.id)}
              className={`px-2.5 py-1 rounded-md transition ${
                domainHint === d.id
                  ? 'bg-blue-600/20 border border-blue-500/50 text-blue-300 font-medium'
                  : 'bg-slate-800/60 border border-slate-700/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>

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
