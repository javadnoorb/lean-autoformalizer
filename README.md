# Lean 4 Autoformalizer & Automated Theorem Prover

A web application that takes informal mathematical theorems stated in plain English (or LaTeX), autoformalizes them into idiomatic **Lean 4** code, and provides automated theorem proving using fast hammer tactics (`omega`, `rfl`, `simp`, `aesop`) and LLM proof search with compiler diagnostics feedback.

---

## Features

- **English to Lean 4 Autoformalization**:
  - Translates natural English math statements into valid Lean 4 syntax.
  - Generates self-contained definitions and idiomatic theorem signatures ending with `:= by sorry`.
  - Powered by Gemini 2.5 (`google-genai` SDK) with few-shot Mathlib-aligned prompts and automatic compiler error self-repair.
- **Lean 4 Verification & Goal Inspection**:
  - Runs the native Lean 4.33 toolchain on Linux.
  - Real-time compiler diagnostics (line & column error markers, warnings).
  - Emulates the **Lean Infoview**: renders open tactic states (`⊢ ...`) and hypothesis contexts.
- **Automated Theorem Prover**:
  - **Fast Hammer Engine**: Rapidly tries decision procedures (`omega` for Presburger arithmetic on `Nat`/`Int`, `rfl` for definitional equalities, `simp`, and `aesop`).
  - **LLM Proof Search**: Optional multi-step tactic synthesis guided by remaining goal states and compiler feedback.
  - **Execution Trace**: Visual breakdown of every tactic attempt, status, and duration in milliseconds.
- **LeanDojo Harness**:
  - Architecture ready for LeanDojo integration (`lean-dojo`) for stepping through interactive tactic states.
- **Interactive UI**:
  - Monaco code editor with custom Lean 4 syntax highlighting and keyword tokenization.
  - Preset example theorems across Arithmetic, Algebra, Logic, and Number Theory.
  - Settings modal to enter custom Gemini API keys or choose models (`gemini-2.5-flash`, `gemini-2.5-pro`).

---

## Quick Start

These instructions target Linux (including WSL2). Everything runs natively — no Windows-specific tooling is needed.

### Prerequisites

- **Python 3.12+** and `pip`
- **Node.js 18+** and `npm`
- **Lean 4 toolchain** via [elan](https://github.com/leanprover/elan):
  ```bash
  curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
  source "$HOME/.elan/env"
  lean --version
  ```

### 1. Configure environment variables

Create a `.env` file in `backend/` (see `backend/app/config.py` for all options):
```bash
GEMINI_API_KEY=your-gemini-api-key
LEAN_BIN=~/.elan/bin/lean
```

### 2. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Backend API docs will be live at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend (React + Vite)

In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
Open browser at: [http://localhost:3000](http://localhost:3000)

---

## Deployment

To host a mock-mode instance (no Lean/Mathlib toolchain required) on a
cloud VM via Docker, see [`deploy/README.md`](deploy/README.md).

---

## Running Tests

To run the backend test suite:
```bash
cd /path/to/lean-autoformalizer/backend
PYTHONPATH=. pytest -v
```

To build the frontend production bundle:
```bash
cd /path/to/lean-autoformalizer/frontend
npm run build
```
