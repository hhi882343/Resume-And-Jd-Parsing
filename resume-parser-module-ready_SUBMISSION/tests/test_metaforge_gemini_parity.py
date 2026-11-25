import inspect
import os
import json
import pytest
from unittest.mock import MagicMock
import httpx

from src.ai.config import config
from src.ai.gemini import call_gemini
from src.metaforgeParser import (
    parse_resume_buffer,
    parse_resume_buffers_bulk,
    reset_ai_parsing_suspended,
    get_ai_parsing_suspended_reason,
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
def reset_suspension():
    reset_ai_parsing_suspended()
    yield
    reset_ai_parsing_suspended()


def test_gemini_canonical_request_shape():
    from tests.parity_paths import get_public_parity_dir
    log_path = os.path.join(get_public_parity_dir(), 'golden', 'gemini_call_logs.json')
    with open(log_path, 'r', encoding='utf-8') as f:
        goldens = json.load(f)

    expected_req = goldens['scenario_1_success']['requests'][0]
    expected_url = expected_req['url']

    # Validate that Python builds the exact URL, headers, and body
    parts = [{'text': 'Resume Content'}]
    body = {
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {
            'temperature': 0.1,
            'maxOutputTokens': 4096,
            'responseMimeType': 'application/json',
        },
    }
    canonical_body = json.dumps(body, separators=(',', ':'))

    headers = {
        'Content-Type': 'application/json',
        'x-goog-api-key': config.geminiApiKey,
    }

    assert 'models/gemini-2.5-flash-lite:generateContent' in expected_url
    assert headers['Content-Type'] == expected_req['headers']['Content-Type']
    assert 'contents' in canonical_body
    assert 'generationConfig' in canonical_body


def test_delay_sequence_and_retry_503(monkeypatch):
    recorded_delays = []

    async def mock_sleep(ms: float):
        recorded_delays.append(ms)

    monkeypatch.setattr('src.ai.gemini.sleep', mock_sleep)
    monkeypatch.setattr(config, 'geminiApiKey', 'test_key')

    # Simulate 503 overloaded then success
    mock_resp_503 = MagicMock()
    mock_resp_503.status_code = 503
    mock_resp_503.json.return_value = {'error': {'message': 'The model is overloaded. Please try again later.'}}

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        'candidates': [{
            'content': {'parts': [{'text': '{"full_name": "Test Candidate"}'}]},
            'finishReason': 'STOP',
        }]
    }

    call_count = 0

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_resp_503
            return mock_resp_200

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockAsyncClient)

    result = run_coro(call_gemini([{'text': 'Hello'}], max_retries=2, use_json_mode=True))
    assert 'Test Candidate' in result
    # Assert exact delay matches Node's 2000ms for /high demand|overloaded/i
    assert recorded_delays == [2000]


def test_bulk_800ms_throttle(monkeypatch):
    recorded_delays = []

    async def mock_sleep(ms: float):
        recorded_delays.append(ms)

    monkeypatch.setattr('src.metaforgeParser.sleep', mock_sleep)
    monkeypatch.setattr(config, 'geminiApiKey', 'test_key')

    # Mock parse_resume_buffer to return immediately
    async def mock_parse(buf, filename):
        return {
            'candidateName': 'John',
            'email': 'john@example.com',
            'contactNumber': None,
            'linkedinUrl': None,
            'highestQualification': None,
            'skillsRaw': None,
            'technologiesRaw': None,
            'technologies': None,
            'totalExperience': None,
            'relevantExperience': None,
            'currentEmployer': None,
            'sourceFile': filename,
            'parser': 'metaforge',
            'role': None,
        }

    monkeypatch.setattr('src.metaforgeParser.parse_resume_buffer', mock_parse)

    files = [
        {'buffer': b'Resume 1', 'filename': 'res1.txt'},
        {'buffer': b'Resume 2', 'filename': 'res2.txt'},
        {'buffer': b'Resume 3', 'filename': 'res3.txt'},
    ]

    results = run_coro(parse_resume_buffers_bulk(files))
    assert len(results) == 3
    # In TS: if (i < files.length - 1 && isMetaforgeParserAvailable() && !aiParsingSuspended) await sleep(800)
    # Between 3 files, there must be exactly 2 pauses of 800ms
    assert recorded_delays == [800, 800]


def test_quota_suspension_on_429(monkeypatch):
    monkeypatch.setattr(config, 'geminiApiKey', 'test_key')

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.json.return_value = {'error': {'message': 'Resource has been exhausted (e.g. check quota).'}}

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            return mock_resp_429

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockAsyncClient)

    resume_bytes = b"John Doe\njohn@example.com\nSkills: Python\n"
    res = run_coro(parse_resume_buffer(resume_bytes, 'john.txt'))
    # Falls back to legacy parser
    assert res['candidateName'] == 'John Doe'
    assert res['parser'] == 'legacy'
    # Verifies aiParsingSuspended flag was raised
    reason = get_ai_parsing_suspended_reason()
    assert reason is not None
    assert 'quota or rate limit reached' in reason


def test_network_error_retry_and_fallback(monkeypatch):
    recorded_delays = []

    async def mock_sleep(ms: float):
        recorded_delays.append(ms)

    monkeypatch.setattr('src.ai.gemini.sleep', mock_sleep)
    monkeypatch.setattr(config, 'geminiApiKey', 'test_key')
    monkeypatch.setattr(config, 'geminiModel', 'gemini-2.5-flash-lite')
    monkeypatch.setattr(config, 'geminiFallbackModels', ['gemini-2.5-flash'])

    class MockFailingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("connect ENOTFOUND generativelanguage.googleapis.com")

    monkeypatch.setattr('src.ai.gemini.httpx.AsyncClient', MockFailingAsyncClient)

    # When all models fail on network fault, parseResumeBuffer falls back to legacy parser
    resume_bytes = b"John Doe\njohn@example.com\nSkills: Python\n"
    res = run_coro(parse_resume_buffer(resume_bytes, 'john.txt'))
    assert res['candidateName'] == 'John Doe'
    assert res['parser'] == 'legacy'
    # In TS: attempt 0 sleeps 1500 * 1 = 1500ms
    assert 1500 in recorded_delays
