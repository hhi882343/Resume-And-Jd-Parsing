import inspect
import pytest
from src.parseCoreResumeFields import extractCurrentLocation
from src.extractResumeText import extractPlainTextFromResumeBuffer
from src.metaforgeParser import parseResumeBuffer
from src.adapters.candidateStoreAdapter import InMemoryCandidateStore
from src.jsRegex import compile_re
from src.ai.config import config


def run_coro(coro):
    stack = [coro]
    val = None
    exc = None
    while stack:
        curr = stack[-1]
        try:
            if exc:
                res = curr.throw(exc)
                exc = None
            else:
                res = curr.send(val)
            if inspect.isawaitable(res):
                stack.append(res)
                val = None
            else:
                val = res
        except StopIteration as e:
            stack.pop()
            val = e.value
            exc = None
        except Exception as e:
            stack.pop()
            exc = e
    if exc:
        raise exc
    return val


@pytest.fixture(autouse=True)
def fallback_mode(monkeypatch):
    """Ensure tests run deterministically in fallback mode by default."""
    monkeypatch.setattr(config, "geminiApiKey", "")
    monkeypatch.setattr(config, "gemini_api_key", "")


# ----------------------------------------------------------------------------
# 1. Location Extraction Rules
# ----------------------------------------------------------------------------

def test_1_extracts_location_from_labeled_current_location_field():
    text = '\n'.join([
        'Harish Sharma',
        'Email: harish@gmail.com',
        'Current Location: Bangalore, Karnataka',
        'Total Experience: 6 years',
    ])
    loc = extractCurrentLocation(text)
    assert loc == 'Bangalore, Karnataka'


def test_2_extracts_location_from_labeled_location_field():
    text = '\n'.join([
        'Divya Nair',
        'Email: divya@gmail.com',
        'Location: Hyderabad, Telangana',
    ])
    loc = extractCurrentLocation(text)
    assert loc == 'Hyderabad, Telangana'


def test_3_extracts_location_from_based_in_phrasing():
    text = '\n'.join([
        'Rohan Varma',
        'Email: rohan@gmail.com',
        'Based in: Pune, Maharashtra',
    ])
    loc = extractCurrentLocation(text)
    assert loc == 'Pune, Maharashtra'


def test_4_returns_null_when_no_location_is_mentioned():
    text = '\n'.join([
        'Amit Patel',
        'Email: amit@gmail.com',
        'Skills: Python, Django',
    ])
    loc = extractCurrentLocation(text)
    assert loc is None


# ----------------------------------------------------------------------------
# 2. Text Document Pipeline with Location & Evidence Lock
# ----------------------------------------------------------------------------

def test_5_extracts_text_and_parses_all_fields_including_location_from_a_text_buffer():
    resume_text = '\n'.join([
        'Kunal Deshmukh',
        'kunal.deshmukh@gmail.com',
        '+91 9876543210',
        'Current Location: Pune, Maharashtra',
        'https://linkedin.com/in/kunaldeshmukh',
        '',
        'Professional Summary',
        'Senior Cloud Engineer with 7 years of experience in enterprise systems.',
        '',
        'Technical Skills',
        'AWS, Terraform, Kubernetes, Docker, Python, Bash, CI/CD, Ansible, Prometheus, Grafana, Linux',
        '',
        'Education',
        'B.E. in Information Technology from Pune University (2014 - 2018)',
    ])

    buffer = resume_text.encode('utf-8')
    text_result = run_coro(extractPlainTextFromResumeBuffer(buffer, 'kunal.txt'))
    assert 'Kunal Deshmukh' in text_result['text']

    parsed = run_coro(parseResumeBuffer(buffer, 'kunal.txt'))
    assert parsed['candidateName'] == 'Kunal Deshmukh'
    assert parsed['email'] == 'kunal.deshmukh@gmail.com'
    assert parsed['contactNumber'] == '+919876543210'
    assert parsed['currentLocation'] == 'Pune, Maharashtra'
    assert parsed['location'] == 'Pune, Maharashtra'
    assert parsed['technologiesRaw'] == 'Senior Cloud Engineer'
    assert compile_re(r'7\s*years', 'i').search(parsed['totalExperience'] or '')
    assert compile_re(r'B\.?\s*E', 'i').search(parsed['highestQualification'] or '')

    # Verify strict 10-skill cap
    skills_array = [s.strip() for s in (parsed['skillsRaw'] or '').split(',') if s.strip()]
    assert len(skills_array) <= 10
    assert 'AWS' in skills_array
    assert 'Terraform' in skills_array
    assert 'Kubernetes' in skills_array


# ----------------------------------------------------------------------------
# 3. Error Handling and Corrupt Buffer Resilience
# ----------------------------------------------------------------------------

def test_6_returns_informative_error_when_buffer_is_corrupt_or_unreadable():
    corrupt_buffer = bytes([0x00, 0x01, 0x02, 0x03])
    res = run_coro(extractPlainTextFromResumeBuffer(corrupt_buffer, 'corrupt.pdf'))
    assert 'text' in res


# ----------------------------------------------------------------------------
# 4. Candidate Store Adapter (Persistence)
# ----------------------------------------------------------------------------

def test_7_persists_and_retrieves_candidates_using_in_memory_candidate_store():
    store = InMemoryCandidateStore()
    mock_candidate = {
        'candidateName': 'Test Candidate',
        'email': 'test@gmail.com',
        'contactNumber': '+919999999999',
        'linkedinUrl': None,
        'highestQualification': 'B.Tech',
        'skillsRaw': 'JavaScript, TypeScript',
        'technologiesRaw': 'Full Stack Engineer',
        'totalExperience': '5 years',
        'relevantExperience': None,
        'currentEmployer': 'Acme Corp',
        'currentLocation': 'Bangalore',
        'sourceFile': 'test.pdf',
        'parser': 'legacy',
    }

    save_res = run_coro(store.saveCandidate(mock_candidate))
    assert 'id' in save_res
    cand_id = save_res['id']

    retrieved = run_coro(store.getCandidateById(cand_id))
    assert retrieved is not None
    assert retrieved['candidateName'] == 'Test Candidate'
    assert retrieved['currentLocation'] == 'Bangalore'

    cand_list = run_coro(store.listCandidates())
    assert len(cand_list) == 1

    deleted = run_coro(store.deleteCandidate(cand_id))
    assert deleted is True

    after_delete = run_coro(store.getCandidateById(cand_id))
    assert after_delete is None
