@echo off
echo =======================================================
echo   Lean 4 Autoformalizer ^& Automated Theorem Prover
echo =======================================================
echo.

echo Starting FastAPI Backend (WSL2 Python)...
start "Lean Backend" wsl -d Ubuntu -- bash -c "cd /mnt/c/Users/javad/.gemini/antigravity/scratch/lean-autoformalizer/backend && /home/javad/miniconda3/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo Starting Vite Frontend (Port 3000)...
start "Lean Frontend" cmd /k "cd /d C:\Users\javad\.gemini\antigravity\scratch\lean-autoformalizer\frontend && npm run dev"

echo.
echo =======================================================
echo   Application launched!
echo   Frontend: http://localhost:3000
echo   Backend API: http://localhost:8000/docs
echo =======================================================
echo.
pause
