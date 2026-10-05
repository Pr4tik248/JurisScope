"""Provider contracts and explicitly labeled local demonstration corpus."""
from dataclasses import dataclass
from typing import Protocol
import html
import os
import re
import httpx
from html.parser import HTMLParser

@dataclass
class LegalDocument:
    source_id: str
    title: str
    jurisdiction: str
    country: str
    region: str = ""
    court: str = ""
    date: str = ""
    document_type: str = ""
    act: str = ""
    section: str = ""
    text: str = ""
    source_url: str = ""
    approved: bool = False

class LegalSourceProvider(Protocol):
    def search(self, query: str, country: str, region: str | None = None) -> list[LegalDocument]: ...
    def get_document(self, source_id: str) -> LegalDocument | None: ...
    def get_metadata(self, source_id: str) -> dict | None: ...

class MockLegalProvider:
    """Synthetic fixtures for UI/dev flow; never presented as real authority."""
    docs = [
        LegalDocument("demo-in-001", "Demonstration: Tenant notice scenario", "India (illustrative)", "India", "Telangana", "", "", "mock", "", "", "Synthetic demonstration content only. This is not a statute or legal authority. Real legal sources are not configured.", "", True),
        LegalDocument("demo-us-001", "Demonstration: US lease scenario", "United States (illustrative)", "United States", "", "", "", "mock", "", "", "Synthetic demonstration content only. This is not a statute or legal authority. Real legal sources are not configured.", "", True),
    ]
    def search(self, query, country, region=None):
        return [d for d in self.docs if d.country.casefold() == country.casefold() and (not region or not d.region or d.region.casefold() == region.casefold())]
    def get_document(self, source_id):
        return next((d for d in self.docs if d.source_id == source_id), None)
    def get_metadata(self, source_id):
        d = self.get_document(source_id)
        return vars(d) if d else None

class IndianKanoonProvider:
    """Integration seam only. No API client is claimed until access is configured."""
    def __init__(self, api_key: str | None = None): self.api_key = api_key
    def search(self, query, country, region=None): return []
    def get_document(self, source_id): return None
    def get_metadata(self, source_id): return None

class OfficialCourtProvider(IndianKanoonProvider):
    """Adapter contract for approved court repositories."""

class OfficialGovernmentProvider(IndianKanoonProvider):
    """Adapter contract for official legislation/government repositories."""

class ProviderUnavailable(RuntimeError):
    """A configured legal source could not be reached or returned invalid data."""

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip_depth += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip_depth:
            self.skip_depth -= 1
        elif tag in ("p", "div", "br", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")
    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)

class CongressGovProvider:
    """Official US federal public-law search through the Congress.gov API.

    Searches enacted Public Laws by title (Congress.gov does not provide a
    full-text search endpoint), then fetches the enrolled bill text. State law
    and court-opinion coverage are outside this provider's scope.
    """
    BASE_URL = "https://api.congress.gov/v3"
    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else os.getenv("CONGRESS_API_KEY", "")
        self.client = client or httpx.Client(timeout=20.0, follow_redirects=True)
        self._owns_client = client is None
        self._documents: dict[str, LegalDocument] = {}

    def _json(self, path: str, **params):
        if not self.api_key:
            raise ProviderUnavailable("Congress.gov API key is not configured")
        try:
            response = self.client.get(f"{self.BASE_URL}/{path.lstrip('/')}", params={**params, "api_key": self.api_key, "format": "json"})
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable("Congress.gov request failed") from exc

    @staticmethod
    def _terms(query: str) -> set[str]:
        ignored = {"the", "and", "for", "with", "from", "that", "this", "what", "does", "under", "about", "law", "legal", "act"}
        return {word for word in re.findall(r"[a-z0-9]+", query.casefold()) if len(word) > 2 and word not in ignored}

    def search(self, query: str, country: str, region: str | None = None) -> list[LegalDocument]:
        if country.casefold() != "united states":
            return []
        current = self._json("congress/current").get("congress", {})
        congress = current.get("number")
        if not congress:
            raise ProviderUnavailable("Congress.gov did not identify the current Congress")
        bills = self._json(f"law/{congress}", limit=250).get("bills", [])
        terms = self._terms(query)
        min_overlap = 1 if len(terms) <= 2 else max(2, (len(terms) + 3) // 4)
        candidates = []
        for bill in bills:
            laws = bill.get("laws", [])
            if not any(law.get("type") == "Public Law" for law in laws):
                continue
            title_terms = self._terms(bill.get("title", ""))
            overlap = len(terms & title_terms)
            if overlap >= min_overlap:
                candidates.append((overlap, bill))
        candidates.sort(key=lambda item: (item[0], item[1].get("latestAction", {}).get("actionDate", "")), reverse=True)
        documents = []
        for _, bill in candidates[:3]:
            doc = self._load_enacted_law(bill)
            if doc:
                documents.append(doc)
        return documents

    def _load_enacted_law(self, bill: dict) -> LegalDocument | None:
        congress, kind, number = bill.get("congress"), bill.get("type", "").lower(), bill.get("number")
        if not congress or not kind or not number:
            return None
        details = self._json(f"bill/{congress}/{kind}/{number}/text").get("textVersions", [])
        # Only use the enrolled version for an item confirmed as a Public Law.
        enrolled = next((version for version in details if version.get("type") == "Enrolled Bill"), None)
        if not enrolled:
            return None
        text_url = next((fmt.get("url") for fmt in enrolled.get("formats", []) if fmt.get("type") == "Formatted Text"), None)
        if not text_url:
            return None
        try:
            response = self.client.get(text_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailable("Congress.gov enrolled text could not be downloaded") from exc
        parser = _TextExtractor()
        parser.feed(response.text)
        text = html.unescape(" ".join(" ".join(parser.parts).split()))
        if not text:
            return None
        law = next((item for item in bill.get("laws", []) if item.get("type") == "Public Law"), {})
        source_id = f"congress-{congress}-{kind}-{number}"
        doc = LegalDocument(
            source_id=source_id,
            title=bill.get("title", f"Public Law {law.get('number', '')}"),
            jurisdiction="United States federal",
            country="United States",
            date=bill.get("latestAction", {}).get("actionDate", ""),
            document_type="enacted_public_law",
            act=f"Public Law {law.get('number', '')}".strip(),
            text=text[:100000],
            source_url=f"https://www.congress.gov/bill/{congress}th-congress/{'senate-bill' if kind == 's' else 'house-bill'}/{number}",
            approved=True,
        )
        self._documents[source_id] = doc
        return doc

    def get_document(self, source_id: str) -> LegalDocument | None:
        return self._documents.get(source_id)

    def get_metadata(self, source_id: str) -> dict | None:
        doc = self.get_document(source_id)
        if not doc:
            return None
        metadata = vars(doc).copy()
        metadata.pop("text", None)
        return metadata

class LegalProviderRouter:
    """Routes each search to the provider for its selected country."""
    def __init__(self, india: LegalSourceProvider, united_states: LegalSourceProvider):
        self.providers = {"india": india, "united states": united_states}
    def search(self, query, country, region=None):
        provider = self.providers.get(country.casefold())
        return provider.search(query, country, region) if provider else []
    def get_document(self, source_id):
        for provider in self.providers.values():
            doc = provider.get_document(source_id)
            if doc:
                return doc
        return None
    def get_metadata(self, source_id):
        for provider in self.providers.values():
            metadata = provider.get_metadata(source_id)
            if metadata:
                return metadata
        return None
