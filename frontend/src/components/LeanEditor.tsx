import React, { useState } from 'react';
import Editor from '@monaco-editor/react';
import { Copy, Check, Play, CheckCircle, Zap, Shield, Info, Loader2 } from 'lucide-react';

interface LeanEditorProps {
  code: string;
  onChange: (val: string) => void;
  onVerify: () => void;
  onProve: (strategy: string) => void;
  isVerifying: boolean;
  isProving: boolean;
  explanation?: string;
}

export const LeanEditor: React.FC<LeanEditorProps> = ({
  code,
  onChange,
  onVerify,
  onProve,
  isVerifying,
  isProving,
  explanation,
}) => {
  const [copied, setCopied] = useState(false);
  const [strategy, setStrategy] = useState<'fast_hammer' | 'llm_refinement'>('fast_hammer');

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const beforeMount = (monaco: any) => {
    // Register Lean 4 language syntax if not already registered
    if (!monaco.languages.getLanguages().some((l: any) => l.id === 'lean4')) {
      monaco.languages.register({ id: 'lean4' });
      monaco.languages.setMonarchTokensProvider('lean4', {
        keywords: [
          'theorem', 'def', 'lemma', 'axiom', 'inductive', 'structure', 'class',
          'instance', 'where', 'with', 'by', 'sorry', 'have', 'show', 'from',
          'match', 'if', 'then', 'else', 'open', 'import', 'variable', 'namespace',
          'end', 'universe', 'example'
        ],
        typeKeywords: [
          'Prop', 'Type', 'Nat', 'Int', 'Real', 'Bool', 'List', 'String', 'Set'
        ],
        tactics: [
          'intro', 'intros', 'exact', 'apply', 'cases', 'rcases', 'induction',
          'rfl', 'simp', 'omega', 'linarith', 'ring', 'aesop', 'decide',
          'rw', 'rewrite', 'assumption', 'trivial', 'contradiction', 'constructor',
          'exists', 'ext', 'funext'
        ],
        tokenizer: {
          root: [
            [/--.*$/, 'comment'],
            [/\/-[\s\S]*?-\//, 'comment'],
            [/\b(theorem|def|lemma|example)\b/, 'keyword.declaration'],
            [/\b(by|sorry)\b/, 'keyword.control'],
            [/\b(Prop|Type|Nat|Int|Real|Bool|List|Set)\b/, 'type'],
            [/\b(rfl|omega|simp|aesop|decide|linarith|ring|intro|cases|exact)\b/, 'keyword.tactic'],
            [/[{}()\[\]]/, '@brackets'],
            [/[0-9]+/, 'number'],
            [/".*?"/, 'string'],
            [/[∀∃∧∨¬→↔≤≥≠∣]/, 'operator'],
          ]
        }
      });
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-md flex flex-col h-[520px]">
      {/* Editor Toolbar */}
      <div className="bg-slate-950 border-b border-slate-800 px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="flex space-x-1.5 mr-2">
            <div className="w-2.5 h-2.5 rounded-full bg-slate-700"></div>
            <div className="w-2.5 h-2.5 rounded-full bg-slate-700"></div>
            <div className="w-2.5 h-2.5 rounded-full bg-slate-700"></div>
          </div>
          <span className="font-mono text-xs text-slate-300 font-medium">Theorem.lean</span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-2">
          <button
            onClick={handleCopy}
            className="p-1.5 text-slate-400 hover:text-slate-200 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-md transition"
            title="Copy Lean Code"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>

          {/* Quick Verify */}
          <button
            onClick={onVerify}
            disabled={isVerifying || isProving || !code.trim()}
            className="flex items-center space-x-1.5 px-3 py-1 text-xs font-medium text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-md transition disabled:opacity-50"
          >
            {isVerifying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Shield className="w-3.5 h-3.5 text-blue-400" />}
            <span>Verify</span>
          </button>

          {/* Strategy Selector */}
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value as any)}
            className="bg-slate-900 text-slate-300 text-xs border border-slate-700 rounded-md px-2 py-1 outline-none focus:border-blue-500 cursor-pointer"
          >
            <option value="fast_hammer">⚡ Fast Hammer (omega, rfl, simp, aesop)</option>
            <option value="llm_refinement">🤖 LLM Proof Search</option>
          </select>

          {/* Auto-Prove Button */}
          <button
            onClick={() => onProve(strategy)}
            disabled={isProving || isVerifying || !code.trim()}
            className="flex items-center space-x-1.5 px-3.5 py-1 text-xs font-semibold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 rounded-md transition shadow-sm disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
          >
            {isProving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Proving...</span>
              </>
            ) : (
              <>
                <Zap className="w-3.5 h-3.5 text-emerald-200 fill-emerald-200" />
                <span>Auto-Prove</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Monaco Code Editor */}
      <div className="flex-1 w-full bg-[#0d1117]">
        <Editor
          height="100%"
          language="lean4"
          theme="vs-dark"
          value={code}
          onChange={(val) => onChange(val || '')}
          beforeMount={beforeMount}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "'Fira Code', monospace",
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            automaticLayout: true,
            tabSize: 2,
            padding: { top: 12, bottom: 12 },
          }}
        />
      </div>

      {/* Explanation Banner */}
      {explanation && (
        <div className="bg-slate-950/90 border-t border-slate-800 px-4 py-2 flex items-start space-x-2 text-xs text-slate-400">
          <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
          <span className="leading-relaxed line-clamp-2">{explanation}</span>
        </div>
      )}
    </div>
  );
};
