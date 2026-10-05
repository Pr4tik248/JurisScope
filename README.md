# Juriscope — source-grounded MVP

GitHub: https://github.com/Pr4tik248/JurisScope

An incremental local MVP with a Next.js interface and a FastAPI service. Gemini and a Congress.gov provider for enacted U.S. federal public laws are connected. India remains mocked; no Indian source, U.S. state law, or court-opinion provider is connected.

## Project structure

```text
backend/app/{api*,ai,database,legal,retrieval,schemas.py,security,services}/
backend/tests/test_api.py
frontend/app/{page.tsx,layout.tsx,globals.css}
```

## Setup

1. Create a Python virtual environment in `backend`, activate it, then run `pip install -r requirements.txt`.
2. Copy `backend/.env.example` to `backend/.env`. Keep secrets there; never use `NEXT_PUBLIC_` for secrets.
3. Start the API from `backend`: `uvicorn app.main:app --reload` (http://localhost:8000).
4. In another terminal, from `frontend`, run `npm install` then `npm run dev` (http://localhost:3000).
5. Optional frontend API override: `NEXT_PUBLIC_API_URL=http://localhost:8000`.

## Environment variables

`GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODELS`, `CONGRESS_API_KEY`, `DATABASE_URL`, `INDIAN_KANOON_API_KEY`, and `RATE_LIMIT_PER_MINUTE`. Never put these keys in frontend variables. Gemini calls are made only when relevant approved documents are retrieved.

## Request flow

The browser submits to `POST /api/legal/ask`; Pydantic validates fields, the jurisdiction resolver canonicalizes country/region, a lightweight scope gate rejects unrelated questions, and the provider interface searches only that jurisdiction. U.S. requests use the Congress.gov API to find enacted Public Laws by title, then fetch enrolled law text. Retrieval rechecks jurisdiction and approval. No relevant source means a structured insufficient-sources response. Gemini receives only retrieved documents; its JSON is schema-validated and citations are checked against retrieved IDs, titles, and section text before returning. If a Gemini model is temporarily unavailable, configured fallback models are tried.

## Current limits and connecting sources

- **Connected:** Congress.gov API for U.S. enacted federal Public Laws. It does not provide state statutes or case opinions. Search matches law titles because Congress.gov does not expose full-text search through this integration; it then retrieves the enrolled text.
- **Mocked/not connected:** India sources (Indian Kanoon credentials and provider implementation still required), official court opinions, PostgreSQL persistence, chunking and embedding ingestion/vector search. `backend/app/database/schema.sql` defines the intended pgvector schema.
- The provider protocol lives in `backend/app/legal/sources.py`; implement `search`, `get_document`, and `get_metadata` for each permitted source. Add approval and provenance checks before indexing.

## Tests

From `backend`: `pytest`. Tests cover jurisdiction scoping, the Congress.gov provider contract, non-legal input, empty question, insufficient sources, citation rejection, prompt-injection treatment, and failure behavior.
