import React, { useState } from 'react';
import { X, Key, Cpu, Terminal, Check } from 'lucide-react';
import { SystemStatus } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  status: SystemStatus | null;
  customApiKey: string;
  onSaveApiKey: (key: string) => void;
  selectedModel: string;
  onSaveModel: (model: string) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  status,
  customApiKey,
  onSaveApiKey,
  selectedModel,
  onSaveModel,
}) => {
  const [apiKeyInput, setApiKeyInput] = useState(customApiKey);
  const [modelInput, setModelInput] = useState(selectedModel);
  const [saved, setSaved] = useState(false);

  if (!isOpen) return null;

  const handleSave = () => {
    onSaveApiKey(apiKeyInput.trim());
    onSaveModel(modelInput);
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 800);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <Key className="w-5 h-5 text-blue-400" />
            <h3 className="font-semibold text-slate-100 text-base">Configuration & Settings</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1 rounded-md transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* API Key */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-slate-300 flex items-center justify-between">
            <span>Gemini API Key</span>
            {status?.gemini_key_configured && (
              <span className="text-[11px] text-emerald-400">Server env key active</span>
            )}
          </label>
          <input
            type="password"
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            placeholder="AIzaSy..."
            className="w-full bg-slate-950 border border-slate-800 focus:border-blue-500 rounded-lg px-3 py-2 text-sm text-slate-100 outline-none font-mono"
          />
          <p className="text-[11px] text-slate-500">
            Stored locally in your browser. Leave blank to use server environment key.
          </p>
        </div>

        {/* Model Selection */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-slate-300 flex items-center space-x-1.5">
            <Cpu className="w-3.5 h-3.5 text-blue-400" />
            <span>Gemini Model</span>
          </label>
          <select
            value={modelInput}
            onChange={(e) => setModelInput(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 focus:border-blue-500 rounded-lg px-3 py-2 text-xs text-slate-200 outline-none cursor-pointer"
          >
            <option value="gemini-2.5-flash">gemini-2.5-flash (Fast & Accurate)</option>
            <option value="gemini-2.5-pro">gemini-2.5-pro (Deep Mathematical Reasoning)</option>
            <option value="gemini-1.5-flash">gemini-1.5-flash</option>
            <option value="gemini-1.5-pro">gemini-1.5-pro</option>
          </select>
        </div>

        {/* Lean 4 Environment Status */}
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3.5 space-y-2 text-xs">
          <div className="flex items-center space-x-1.5 text-slate-300 font-medium">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span>Execution Environment</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-slate-400 font-mono text-[11px] pt-1">
            <div>Status: <span className="text-slate-200">{status?.lean_installed ? 'Installed' : 'Mock'}</span></div>
            <div className="col-span-2">
              Lean 4: <span className="text-slate-200">{status?.lean_version || 'Checking / Initializing...'}</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end space-x-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs text-slate-400 hover:text-slate-200 transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition"
          >
            {saved ? <Check className="w-4 h-4 text-emerald-300" /> : null}
            <span>{saved ? 'Saved!' : 'Save Settings'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
