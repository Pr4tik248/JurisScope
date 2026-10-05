from app.legal.sources import LegalSourceProvider, LegalDocument

def retrieve(provider: LegalSourceProvider, question: str, country: str, region: str, limit: int = 5) -> list[LegalDocument]:
    # Provider search is constrained to requested jurisdiction; enforce again at boundary.
    found = provider.search(question, country, region or None)
    # Synthetic fixtures are useful for provider/UI demos, but must never become
    # evidence for an answer, even if accidentally marked approved by a fixture.
    scoped = [d for d in found if d.approved and d.document_type != "mock" and d.country.casefold() == country.casefold() and (not region or not d.region or d.region.casefold() == region.casefold())]
    return scoped[:limit]
