import re
from app.schemas import LegalAnswer
from app.legal.sources import LegalDocument

def validate_citations(answer: LegalAnswer, documents: list[LegalDocument]) -> LegalAnswer:
    allowed = {d.source_id: d for d in documents}
    for cite in answer.legal_basis:
        doc = allowed.get(cite.source_id)
        if not doc:
            raise ValueError("Model returned an unknown source citation")
        if cite.title != doc.title:
            raise ValueError("Citation title does not match retrieved source")
        if cite.section:
            source_text = (doc.section + " " + doc.text).casefold()
            section_text = cite.section.strip().casefold()
            if section_text not in source_text:
                # Normalize common U.S. statutory forms such as "Section 2(a)"
                # against enrolled text headings written as "SECTION 2. ... (a)".
                match = re.fullmatch(r"(?:section|sec\.?\s*)\s*([0-9]+[a-z]*)\s*((?:\([a-z0-9]+\))*)", section_text)
                if not match:
                    raise ValueError("Citation section is not present in retrieved source")
                root, suffixes = match.groups()
                root_pattern = rf"\b(?:section|sec\.?)\s*{re.escape(root)}\b"
                if not re.search(root_pattern, source_text):
                    raise ValueError("Citation section is not present in retrieved source")
                if any(suffix.casefold() not in source_text for suffix in re.findall(r"\([a-z0-9]+\)", suffixes)):
                    raise ValueError("Citation subsection is not present in retrieved source")
    return answer
