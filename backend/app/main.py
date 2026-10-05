import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from app.schemas import AskRequest, SearchRequest, LegalAnswer, Jurisdiction
from app.legal.jurisdiction import resolve
from app.legal.sources import MockLegalProvider, CongressGovProvider, LegalProviderRouter, ProviderUnavailable
from app.retrieval.pipeline import retrieve
from app.services.classifier import is_legal_question, is_greeting
from app.ai.gemini import GeminiService
from app.security.citations import validate_citations

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
app = FastAPI(title="Legal AI API", version="0.1.0")
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{os.getenv('RATE_LIMIT_PER_MINUTE','20')}/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["GET","POST"], allow_headers=["Content-Type"])
provider = LegalProviderRouter(
    india=MockLegalProvider(),
    united_states=CongressGovProvider(),
)
ai = GeminiService()

@app.get("/api/health")
def health(): return {"status":"ok","mode":"congress_us_mock_india","gemini_configured":bool(ai.api_key),"congress_configured":bool(os.getenv("CONGRESS_API_KEY"))}

@app.get("/api/jurisdictions")
def jurisdictions(): return {"countries":[{"name":"India","regions":["Telangana","Andhra Pradesh","Delhi","Karnataka","Maharashtra","Tamil Nadu"]},{"name":"United States","regions":[]}],"roles":["tenant","landlord","employee","employer","consumer","business_owner","plaintiff","defendant","lawyer","student","other"]}

@app.post("/api/legal/search")
@limiter.limit("30/minute")
def search(request: Request, body: SearchRequest):
    try: country, region = resolve(body.country, body.state)
    except ValueError as e: raise HTTPException(422, str(e))
    if not is_legal_question(body.question): return {"documents":[],"message":"This application handles legal-information questions."}
    try: docs = retrieve(provider, body.question, country, region)
    except ProviderUnavailable as e: raise HTTPException(503, str(e))
    return {"documents":[{**vars(d),"demo":d.source_id.startswith("demo-")} for d in docs]}

@app.get("/api/legal/source/{source_id}")
def source(source_id: str):
    doc = provider.get_document(source_id)
    if not doc: raise HTTPException(404,"Source not found")
    return {**vars(doc),"demo":doc.source_id.startswith("demo-")}

@app.post("/api/legal/ask", response_model=LegalAnswer)
@limiter.limit("10/minute")
def ask(request: Request, body: AskRequest):
    try: country, region = resolve(body.country, body.state)
    except ValueError as e: raise HTTPException(422, str(e))
    if is_greeting(body.question):
        return LegalAnswer(jurisdiction=Jurisdiction(country=country,region=region),answer="Hi! I’m Legal AI. Ask me a legal-information question and include your country and state or region so I can look for relevant legal sources.",needs_clarification=False)
    if not is_legal_question(body.question):
        return LegalAnswer(jurisdiction=Jurisdiction(country=country,region=region),answer="This application handles legal-information questions. Please ask a question about a legal issue.",needs_clarification=True)
    try: docs = retrieve(provider, body.question, country, region)
    except ProviderUnavailable as e: raise HTTPException(503, str(e))
    if not docs:
        return LegalAnswer(jurisdiction=Jurisdiction(country=country,region=region),answer="I could not find sufficient approved legal sources to answer this question reliably.",uncertainty="insufficient_sources",needs_clarification=True)
    try:
        result = ai.generate(body.question,country,region,body.role,body.language,docs)
        if result.jurisdiction.country.casefold() != country.casefold(): raise ValueError("Model jurisdiction mismatch")
        return validate_citations(result,docs)
    except ValueError as e:
        raise HTTPException(502, f"Response validation failed: {e}")
    except Exception as e:
        raise HTTPException(503, "Legal answer generation is unavailable. No uncited answer was returned.") from e
