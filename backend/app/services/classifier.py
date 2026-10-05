import re

LEGAL_TERMS = re.compile(r"\b(legal(?:ly)?|law|court|tenant|landlord|evict|eviction|lease|contract|employment|employee|employer|consumer|plaintiff|defendant|rights|liability|sue|notice|statute|section|act|bill|regulation|lawyer|visa|divorce|custody|criminal|tax)\b", re.I)

def is_legal_question(question: str) -> bool:
    return bool(LEGAL_TERMS.search(question))

def is_greeting(question: str) -> bool:
    """Handle simple greetings locally without sending them into legal RAG."""
    return bool(re.fullmatch(r"(?:hi|hello|hey|good morning|good afternoon|good evening)[!. ]*", question.strip(), re.I))
