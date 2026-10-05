from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
def payload(question="Can my landlord evict me without notice?", country="India", state="Telangana"):
    return {"question":question,"country":country,"state":state,"role":"tenant","language":"English"}

def test_indian_legal_question_no_sources_fails_closed():
    r=client.post('/api/legal/ask',json=payload()); assert r.status_code==200; assert r.json()['uncertainty']=='insufficient_sources'
def test_telanganascope():
    r=client.post('/api/legal/search',json={"question":"tenant eviction notice","country":"India","state":"Telangana"}); assert all(d['country']=='India' and (not d['region'] or d['region']=='Telangana') for d in r.json()['documents'])
def test_us_jurisdiction(monkeypatch):
    from app import main
    from app.legal.sources import MockLegalProvider
    monkeypatch.setattr(main,'provider',MockLegalProvider())
    r=client.post('/api/legal/search',json={"question":"tenant eviction notice","country":"United States"}); assert all(d['country']=='United States' for d in r.json()['documents'])
def test_non_legal():
    r=client.post('/api/legal/ask',json=payload("What is the weather today?")); assert r.status_code==200 and not r.json()['legal_basis']
def test_greeting_gets_a_response_without_gemini():
    r=client.post('/api/legal/ask',json=payload("HI")); assert r.status_code==200; assert r.json()['answer'].startswith('Hi!'); assert not r.json()['legal_basis']
def test_statute_section_question_is_classified_as_legal():
    from app.services.classifier import is_legal_question
    assert is_legal_question('Under the Kay Hagan Tick Reauthorization Act, what authorization period does Section 2(a) set?')
def test_empty_question():
    r=client.post('/api/legal/ask',json=payload(" ")); assert r.status_code==422
def test_insufficient_sources():
    r=client.post('/api/legal/ask',json=payload()); assert r.json()['needs_clarification'] is True
def test_fabricated_citation_rejected():
    from app.schemas import LegalAnswer,Jurisdiction,LegalBasis
    from app.security.citations import validate_citations
    import pytest
    with pytest.raises(ValueError): validate_citations(LegalAnswer(jurisdiction=Jurisdiction(country='India'),answer='x',legal_basis=[LegalBasis(source_id='invented',title='fake',explanation='x')]),[])

def test_us_subsection_citation_matches_enrolled_text_heading():
    from app.schemas import LegalAnswer,Jurisdiction,LegalBasis
    from app.legal.sources import LegalDocument
    from app.security.citations import validate_citations
    doc=LegalDocument('us-1','Example Public Law','United States federal','United States',text='SECTION 2. Reauthorization. (a) The Secretary shall act.',approved=True)
    result=LegalAnswer(jurisdiction=Jurisdiction(country='United States'),answer='Supported.',legal_basis=[LegalBasis(source_id='us-1',title='Example Public Law',section='Section 2(a)',explanation='Supported by the enrolled text.')])
    assert validate_citations(result,[doc]) is result
def test_wrong_jurisdiction_source_filtered():
    from app.retrieval.pipeline import retrieve
    from app.legal.sources import MockLegalProvider
    assert retrieve(MockLegalProvider(),'eviction','India','Telangana') == []  # mock is intentionally not real approved law
def test_prompt_injection_is_data_not_instruction():
    from app.ai.gemini import SYSTEM_INSTRUCTION
    assert 'untrusted quoted evidence' in SYSTEM_INSTRUCTION.lower()

def test_congress_provider_uses_enacted_public_law_and_official_text():
    import httpx
    from app.legal.sources import CongressGovProvider
    def handler(request):
        path=request.url.path
        if path.endswith('/congress/current'):
            return httpx.Response(200,json={'congress':{'number':119}})
        if path.endswith('/law/119'):
            return httpx.Response(200,json={'bills':[{'congress':119,'type':'S','number':'7','title':'Tenant Protection Act','latestAction':{'actionDate':'2026-01-01'},'laws':[{'type':'Public Law','number':'119-7'}]}]})
        if path.endswith('/bill/119/s/7/text'):
            return httpx.Response(200,json={'textVersions':[{'type':'Enrolled Bill','formats':[{'type':'Formatted Text','url':'https://example.test/enrolled.html'}]}]})
        if request.url.host == 'example.test':
            return httpx.Response(200,text='<html><body><p>SEC. 1. Tenant notice requirements.</p></body></html>')
        return httpx.Response(404)
    client=httpx.Client(transport=httpx.MockTransport(handler))
    provider=CongressGovProvider(api_key='test-only',client=client)
    docs=provider.search('Tenant Protection Act legal rights','United States')
    assert len(docs)==1 and docs[0].approved
    assert docs[0].act=='Public Law 119-7'
    assert 'SEC. 1. Tenant notice requirements.' in docs[0].text
    assert provider.get_document(docs[0].source_id) is docs[0]

def test_congress_provider_never_returns_us_law_for_india():
    from app.legal.sources import CongressGovProvider
    assert CongressGovProvider(api_key='test-only').search('tenant law','India') == []
def test_gemini_failure_does_not_fallback(monkeypatch):
    from app import main
    from app.legal.sources import LegalDocument
    class Provider:
        def search(self,*args): return [LegalDocument('src-1','Example source','India','India','Telangana',document_type='judgment',text='Example source material',approved=True)]
        def get_document(self,*args): return None
        def get_metadata(self,*args): return None
    monkeypatch.setattr(main,'provider',Provider())
    from app.main import ai
    monkeypatch.setattr(ai,'api_key','test-key')
    def fail(*args,**kwargs): raise RuntimeError('provider down')
    monkeypatch.setattr(ai,'generate',fail)
    r=client.post('/api/legal/ask',json=payload())
    assert r.status_code==503
    assert 'answer' not in r.json()
