import React from 'react';
import { Terminal, KeyRound, Settings as SettingsIcon, CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';
import { SystemStatus } from '../types';

interface HeaderProps {
  status: SystemStatus | null;
  onOpenSettings: () => void;
  hasCustomKey: boolean;
}

export const Header: React.FC<HeaderProps> = ({ status, onOpenSettings, hasCustomKey }) => {
  const isLeanReady = status?.lean_installed;
  const isKeyConfigured = hasCustomKey || status?.gemini_key_configured;

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-40 px-6 py-3.5">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Left Branding */}
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <span className="font-mono text-white font-bold text-lg">∀</span>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="font-semibold text-slate-100 text-lg tracking-tight">Lean 4 Autoformalizer</h1>
              <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                v1.0
              </span>
            </div>
            <p className="text-xs text-slate-400">Plain English Theorem Formalization & Automated Proof Search</p>
          </div>
        </div>

        {/* Right Status Badges & Controls */}
        <div className="flex items-center space-x-4 text-xs">
          {/* Lean Status */}
          <div className="flex items-center space-x-2 px-3 py-1.5 rounded-md bg-slate-900 border border-slate-800">
            <Terminal className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Lean 4:</span>
            {isLeanReady ? (
              <div className="flex items-center space-x-1 text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span className="font-medium font-mono">{status?.lean_version?.split(' ')[1] || 'Ready'}</span>
              </div>
            ) : (
              <div className="flex items-center space-x-1 text-amber-400" title="Initializing toolchain or using fallback validator">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Mock</span>
              </div>
            )}
          </div>

          {/* Gemini API Status */}
          <button
            onClick={onOpenSettings}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-800 transition cursor-pointer"
            title="Configure Gemini API Key"
          >
            <KeyRound className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">LLM:</span>
            {isKeyConfigured ? (
              <div className="flex items-center space-x-1 text-emerald-400">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Connected</span>
              </div>
            ) : (
              <div className="flex items-center space-x-1 text-amber-400">
                <span>Key Missing (Click to Add)</span>
              </div>
            )}
          </button>

          {/* Settings Button */}
          <button
            onClick={onOpenSettings}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition border border-slate-700 hover:border-slate-600"
          >
            <SettingsIcon className="w-3.5 h-3.5" />
            <span>Settings</span>
          </button>
        </div>
      </div>
    </header>
  );
};
