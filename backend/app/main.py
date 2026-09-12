import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.schemas import (
    FormalizeRequest,
    FormalizeResponse,
    ProveRequest,
    ProveResponse,
    VerifyRequest,
    VerifyResponse,
    SystemStatusResponse,
)
from app.services.lean_runner import lean_runner
from app.services.autoformalizer import autoformalizer
from app.services.prover import prover
from app.services.leandojo_harness import leandojo_harness

app = FastAPI(
    title="Lean 4 Autoformalizer & Prover API",
    description="Backend service for translating English math theorems into Lean 4 and automated theorem proving.",
    version="1.0.0",
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status", response_model=SystemStatusResponse)
def get_status():
    lean_stat = lean_runner.get_system_status()
    has_gemini = bool(settings.GEMINI_API_KEY)
    return SystemStatusResponse(
        status="online",
        lean_installed=lean_stat["installed"],
        lean_version=lean_stat.get("version"),
        gemini_key_configured=has_gemini,
        model=settings.GEMINI_MODEL,
    )

@app.get("/api/harness")
def get_harness():
    return leandojo_harness.get_status()

@app.get("/api/examples")
def get_examples():
    return [
        {
            "title": "Addition Identity",
            "category": "Arithmetic",
            "english": "For all natural numbers n, n + 0 = n",
            "hint": "nat_add_zero"
        },
        {
            "title": "Addition Commutativity",
            "category": "Arithmetic",
            "english": "For all natural numbers a and b, a + b = b + a",
            "hint": "nat_add_comm"
        },
        {
            "title": "Square of Even Number",
            "category": "Number Theory",
            "english": "If a natural number n is even, then n squared is also even.",
            "hint": "even_sq_even"
        },
        {
            "title": "Binomial Identity",
            "category": "Algebra",
            "english": "For any natural numbers a and b, (a + b)^2 = a^2 + 2*a*b + b^2",
            "hint": "binomial_expand"
        },
        {
            "title": "Conjunction Commutativity",
            "category": "Logic",
            "english": "For any propositions P and Q, P and Q implies Q and P.",
            "hint": "and_comm"
        },
        {
            "title": "Irrationality of √2",
            "category": "Number Theory",
            "english": "The square root of 2 is irrational (there are no positive integers p and q such that p^2 = 2 * q^2).",
            "hint": "sqrt_2_irrational"
        }
    ]

@app.post("/api/formalize", response_model=FormalizeResponse)
def formalize(req: FormalizeRequest):
    if not req.english_statement.strip():
        raise HTTPException(status_code=400, detail="English theorem statement cannot be empty.")
    return autoformalizer.formalize(req)

@app.post("/api/prove", response_model=ProveResponse)
def prove(req: ProveRequest):
    if not req.lean_code.strip():
        raise HTTPException(status_code=400, detail="Lean code cannot be empty.")
    return prover.prove(req)

@app.post("/api/verify", response_model=VerifyResponse)
def verify(req: VerifyRequest):
    return lean_runner.verify(req.lean_code)

@app.get("/")
def root():
    return {"message": "Lean 4 Autoformalizer & Prover Backend is running."}
