import { FormalizeResponse, ProveResponse, VerifyResponse, SystemStatus, TheoremExample } from '../types';

const API_BASE = '/api';

export async function getSystemStatus(): Promise<SystemStatus> {
  const res = await fetch(`${API_BASE}/status`);
  if (!res.ok) throw new Error('Failed to fetch system status');
  return res.json();
}

export async function getExamples(): Promise<TheoremExample[]> {
  const res = await fetch(`${API_BASE}/examples`);
  if (!res.ok) throw new Error('Failed to fetch examples');
  return res.json();
}

export async function formalizeTheorem(
  englishStatement: string,
  domainHint?: string,
  apiKey?: string,
  model?: string
): Promise<FormalizeResponse> {
  const res = await fetch(`${API_BASE}/formalize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      english_statement: englishStatement,
      domain_hint: domainHint,
      api_key: apiKey || undefined,
      model: model || undefined,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Formalization failed' }));
    throw new Error(err.detail || 'Formalization failed');
  }
  return res.json();
}

export async function proveTheorem(
  leanCode: string,
  strategy: string = 'fast_hammer',
  apiKey?: string,
  model?: string
): Promise<ProveResponse> {
  const res = await fetch(`${API_BASE}/prove`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      lean_code: leanCode,
      strategy: strategy,
      api_key: apiKey || undefined,
      model: model || undefined,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Proving failed' }));
    throw new Error(err.detail || 'Proving failed');
  }
  return res.json();
}

export async function verifyLeanCode(leanCode: string): Promise<VerifyResponse> {
  const res = await fetch(`${API_BASE}/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lean_code: leanCode }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Verification failed' }));
    throw new Error(err.detail || 'Verification failed');
  }
  return res.json();
}
