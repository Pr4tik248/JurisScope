from typing import Literal
from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict

Role = Literal["tenant", "landlord", "employee", "employer", "consumer", "business_owner", "plaintiff", "defendant", "lawyer", "student", "other"]

class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=5000)
    country: str = Field(min_length=2, max_length=80)
    state: str | None = Field(default=None, max_length=100)
    role: Role
    language: str = Field(default="English", min_length=2, max_length=50)

    @field_validator("question", "country", "language", mode="before")
    @classmethod
    def trim_strings(cls, value):
        return value.strip() if isinstance(value, str) else value

class LegalBasis(BaseModel):
    source_id: str
    title: str
    section: str = ""
    explanation: str

class Jurisdiction(BaseModel):
    country: str
    region: str = ""

class LegalAnswer(BaseModel):
    jurisdiction: Jurisdiction
    answer: str
    legal_basis: list[LegalBasis] = Field(default_factory=list)
    important_facts: list[str] = Field(default_factory=list)
    uncertainty: str = ""
    missing_information: list[str] = Field(default_factory=list)
    needs_clarification: bool = False

class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    country: str = Field(min_length=2, max_length=80)
    state: str | None = None
