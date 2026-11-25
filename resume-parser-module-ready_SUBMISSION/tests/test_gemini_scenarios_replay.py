import os
import json
import inspect
import pytest
from unittest.mock import MagicMock
import httpx

from src.ai.config import config
from src.ai.gemini import call_gemini, try_parse
from src.metaforgeParser import (
    parse_resume_buffer,
    reset_ai_parsing_suspended,
    get_ai_parsing_suspended_reason,
    apply_evidence_lock,
)


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
def clean_state():
    reset_ai_parsing_suspended()
    config.geminiApiKey = "test_key"
    config.gemini_api_key = "test_key"
    config.geminiModel = "gemini-2.5-flash-lite"
    config.gemini_model = "gemini-2.5-flash-lite"
    config.geminiFallbackModels = ["gemini-2.5-flash", "gemini-2.0-flash"]
    config.gemini_fallback_models = ["gemini-2.5-flash", "gemini-2.0-flash"]
    yield
    reset_ai_parsing_suspended()


def load_logs():
    from tests.parity_paths import get_public_parity_dir
    log_path = os.path.join(get_public_parity_dir(), 'golden', 'gemini_call_logs.json')
    with open(log_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_scenario_1_success_replay(monkeypatch):
    logs = load_logs()['scenario_1_success']
    recorded_requests = []
    recorded_delays = []

    async def mock_sleep(ms: float):
        recorded_delays.append(ms)

    monkeypatch.setattr('src.ai.gemini.sleep', mock_sleep)

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, headers=None, content=None):
            body_dict = json.loads(content.decode('utf-8') if isinstance(content, bytes) else content)
            recorded_requests.append({
                'url': url,
                'content': content,
                'body': body_dict,
                'headers': headers,
            })
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                'candidates': [{
                    'content': {'parts': [{'text': logs['requests'][0]['response_body_raw']}]},
                    'finishReason': 'STOP',
                }]
            }
            return resp

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockClient)

    parts = [{'text': 'Resume text for Amit Kumar'}]
    res_text = run_coro(call_gemini(parts, max_retries=2, use_json_mode=True))
    assert 'Amit Kumar' in res_text

    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    expected_req = logs['requests'][0]
    assert req['url'] == expected_req['url']
    assert req['headers']['Content-Type'] == expected_req['headers']['Content-Type']
    assert req['body']['generationConfig']['responseMimeType'] == 'application/json'
    assert recorded_delays == []


def test_scenario_2_malformed_json_fallback_plain(monkeypatch):
    logs = load_logs()['scenario_2_malformed_json_pass1_recovers_pass2']
    recorded_requests = []
    recorded_delays = []

    async def mock_sleep(ms: float):
        recorded_delays.append(ms)

    monkeypatch.setattr('src.ai.gemini.sleep', mock_sleep)

    call_count = 0

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, headers=None, content=None):
            nonlocal call_count
            body_dict = json.loads(content.decode('utf-8') if isinstance(content, bytes) else content)
            recorded_requests.append({
                'url': url,
                'content': content,
                'body': body_dict,
                'headers': headers,
            })
            call_count += 1
            resp = MagicMock()
            resp.status_code = 200
            if call_count == 1:
                resp.json.return_value = {
                    'candidates': [{
                        'content': {'parts': [{'text': logs['requests'][0]['response_body_raw']}]},
                        'finishReason': 'STOP',
                    }]
                }
            else:
                resp.json.return_value = {
                    'candidates': [{
                        'content': {'parts': [{'text': logs['requests'][1]['response_body_raw']}]},
                        'finishReason': 'STOP',
                    }]
                }
            return resp

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockClient)

    parts = [{'text': 'Resume text for Rahul Verma'}]
    res = run_coro(try_parse(parts, 'text'))
    assert res['full_name'] == logs['final_output']['candidateName']

    assert len(recorded_requests) == 2
    assert recorded_requests[0]['body']['generationConfig']['responseMimeType'] == 'application/json'
    assert 'responseMimeType' not in recorded_requests[1]['body']['generationConfig']


def test_scenario_2b_both_passes_malformed(monkeypatch):
    logs = load_logs()['scenario_2b_both_passes_malformed_fallback_to_keyword']
    recorded_delays = []

    async def mock_sleep(ms: float):
        recorded_delays.append(ms)

    monkeypatch.setattr('src.ai.gemini.sleep', mock_sleep)

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, headers=None, content=None):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                'candidates': [{
                    'content': {'parts': [{'text': 'Not JSON at all'}]},
                    'finishReason': 'STOP',
                }]
            }
            return resp

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockClient)

    resume_text = "Karan Mehra\nkaran.mehra@example.com\n+91 9876543299\nSkills: Python, SQL, Linux\nProfessional Summary: Software Engineer with 2 years of experience.\nEducation\nB.Tech\n"
    res = run_coro(parse_resume_buffer(resume_text.encode('utf-8'), 'karan.txt'))
    # Falls back to legacy parser
    assert res['candidateName'] == logs['final_output']['candidateName']
    assert res['parser'] == 'legacy'


def test_scenario_3_markdown_fenced_json(monkeypatch):
    logs = load_logs()['scenario_3_markdown_fenced_json']

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, headers=None, content=None):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                'candidates': [{
                    'content': {'parts': [{'text': logs['requests'][0]['response_body_raw']}]},
                    'finishReason': 'STOP',
                }]
            }
            return resp

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockClient)

    parts = [{'text': 'Resume text for Priya Sharma'}]
    res = run_coro(try_parse(parts, 'text'))
    assert res['full_name'] == logs['final_output']['candidateName']
    assert res['skills'] == ['Python', 'PyTorch', 'TensorFlow', 'NLP']


def test_scenario_4_quota_429_suspension(monkeypatch):
    logs = load_logs()['scenario_4_quota_429']

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, headers=None, content=None):
            resp = MagicMock()
            resp.status_code = 429
            resp.json.return_value = {'error': {'message': 'Resource has been exhausted (e.g. check quota).'}}
            return resp

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockClient)

    resume_text = "Vikram Malhotra\nvikram.m@example.com\n+91 98765 12345\nSkills: React, TypeScript, Node.js\n"
    res = run_coro(parse_resume_buffer(resume_text.encode('utf-8'), 'vikram.txt'))
    assert res['candidateName'] == logs['final_output']['candidateName']
    assert res['parser'] == 'legacy'
    assert get_ai_parsing_suspended_reason() is not None


def test_scenario_5_retry_503(monkeypatch):
    logs = load_logs()['scenario_5_retry_503']
    recorded_delays = []

    async def mock_sleep(ms: float):
        recorded_delays.append(ms)

    monkeypatch.setattr('src.ai.gemini.sleep', mock_sleep)

    call_count = 0

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, headers=None, content=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if call_count == 1:
                resp.status_code = 503
                resp.json.return_value = {'error': {'message': 'The model is overloaded. Please try again later.'}}
            else:
                resp.status_code = 200
                resp.json.return_value = {
                    'candidates': [{
                        'content': {'parts': [{'text': logs['requests'][1]['response_body_raw']}]},
                        'finishReason': 'STOP',
                    }]
                }
            return resp

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockClient)

    parts = [{'text': 'Resume text for Sneha Patil'}]
    res = run_coro(call_gemini(parts, max_retries=2, use_json_mode=True))
    assert 'Sneha Patil' in res
    assert recorded_delays == [2000]


def test_scenario_6_fallback_404(monkeypatch):
    logs = load_logs()['scenario_6_fallback_404']
    recorded_requests = []

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, headers=None, content=None):
            recorded_requests.append(url)
            resp = MagicMock()
            if 'gemini-2.5-flash-lite' in url:
                resp.status_code = 404
                resp.json.return_value = {'error': {'message': 'models/gemini-2.5-flash-lite is not found'}}
            else:
                resp.status_code = 200
                resp.json.return_value = {
                    'candidates': [{
                        'content': {'parts': [{'text': logs['requests'][1]['response_body_raw']}]},
                        'finishReason': 'STOP',
                    }]
                }
            return resp

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockClient)

    parts = [{'text': 'Resume text for Arjun Reddy'}]
    res = run_coro(call_gemini(parts, max_retries=2, use_json_mode=True))
    assert 'Arjun Reddy' in res
    assert len(recorded_requests) == 2
    assert 'gemini-2.5-flash-lite' in recorded_requests[0]
    assert 'gemini-2.5-flash' in recorded_requests[1]


def test_scenario_7_hallucinated_values_evidence_lock():
    logs = load_logs()['scenario_7_hallucinated_values']
    raw_text = "Kavita Nair\nkavita.nair@example.com\n+91 98765 43210\nEducation: B.Sc in Physics\nSkills: Python, SQL\nTotal Experience: 3 years\nLocation: New York, USA\n"

    candidate = logs['beforeEvidenceLock']
    locked = apply_evidence_lock(candidate, raw_text)

    # Qualification was hallucinated Ph.D. -> reset to B.Sc in Physics from rawText
    assert locked['highestQualification'] == 'B.Sc in Physics'
    # Experience was hallucinated 15 years -> reset to 3 years from rawText
    assert locked['totalExperience'] == '3 years'
    # Location survives because location lacks a hasTextEvidence check
    assert locked['location'] == 'New York, USA'
    assert locked['currentLocation'] == 'New York, USA'


def test_scenario_8_partial_null_case():
    logs = load_logs()['scenario_8_partial_null_case']
    expected = logs['final_output']
    raw_text = "Jane Smith\njane.smith@example.com\n+91 9876543211\nSummary: Senior Data Engineer with experience in data platforms.\nSkills: Python, SQL, Spark, Kafka\nEducation: M.Tech in Data Science\n"

    candidate = {
        'candidateName': 'Jane Smith',
        'email': 'jane.smith@example.com',
        'contactNumber': None,
        'linkedinUrl': None,
        'highestQualification': None,
        'skillsRaw': None,
        'technologiesRaw': None,
        'technologies': None,
        'totalExperience': None,
        'relevantExperience': None,
        'currentEmployer': None,
        'sourceFile': 'jane.txt',
        'parser': 'metaforge',
        'role': None,
    }
    locked = apply_evidence_lock(candidate, raw_text)
    assert locked['candidateName'] == 'Jane Smith'
    assert locked['email'] == 'jane.smith@example.com'
    assert locked['highestQualification'] == 'M.Tech in Data Science'
    assert 'Python' in locked['skillsRaw']


def test_scenario_9_network_error(monkeypatch):
    logs = load_logs()['scenario_9_network_error_fetch_throws']
    recorded_delays = []
    recorded_requests = []

    async def mock_sleep(ms: float):
        recorded_delays.append(ms)

    monkeypatch.setattr('src.ai.gemini.sleep', mock_sleep)
    config.geminiModel = 'gemini-2.5-flash-lite'
    config.geminiFallbackModels = ['gemini-2.5-flash']

    class MockFailingClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, headers=None, content=None):
            recorded_requests.append(url)
            raise httpx.ConnectError("connect ENOTFOUND generativelanguage.googleapis.com")

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockFailingClient)

    resume_text = "Rohit Sen\nrohit.sen@example.com\n+91 98765 43200\nSkills: Python, Django, PostgreSQL\nTotal Experience: 3 years\nLocation: Kolkata, India\n"
    res = run_coro(parse_resume_buffer(resume_text.encode('utf-8'), 'rohit.txt'))
    assert res['candidateName'] == logs['final_output']['candidateName']
    assert res['parser'] == 'legacy'
    # Primary model attempt 0 sleep 1500, attempt 1 throws -> falls back to legacy
    assert recorded_delays == [1500]
    assert len(recorded_requests) == 2
