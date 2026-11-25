import os
import json
import inspect
from unittest.mock import MagicMock
import pytest
from src.parseCoreResumeFields import parseCoreFieldsFromResumeText
from src.metaforgeParser import parse_resume_buffer, reset_ai_parsing_suspended
from src.ai.config import config
from src.clock import freeze_time
import src.ai.gemini


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


from tests.parity_paths import get_public_parity_dir

pub_parity = get_public_parity_dir()
inputs_dir = os.path.join(pub_parity, 'inputs')
goldens_dir = os.path.join(pub_parity, 'golden', 'path3_parseResumeBuffer_gemini')
golden_files = sorted([f for f in os.listdir(goldens_dir) if f.endswith('.json')]) if os.path.exists(goldens_dir) else []


@pytest.mark.parametrize("gfile", golden_files)
def test_path3_golden_case(gfile):
    config.geminiApiKey = 'mock-key-for-golden-generation'
    config.gemini_api_key = 'mock-key-for-golden-generation'
    reset_ai_parsing_suspended()

    input_id = os.path.splitext(gfile)[0]
    input_path = os.path.join(inputs_dir, f"{input_id}.txt")
    golden_path = os.path.join(goldens_dir, gfile)

    assert os.path.exists(input_path), f"Input file missing: {input_path}"

    with open(input_path, 'r', encoding='utf-8', newline='') as f:
        raw_text = f.read()

    with open(golden_path, 'r', encoding='utf-8') as f:
        expected = json.load(f)

    baseline = parseCoreFieldsFromResumeText(raw_text)
    tot_exp = baseline.get('totalExperienceText') or (
        f"{baseline.get('totalExperienceYears')} years" if baseline.get('totalExperienceYears') else None
    )
    mock_parsed = {
        'full_name': baseline.get('candidateName') or "Candidate",
        'email': baseline.get('email'),
        'contact': baseline.get('contactNumber'),
        'linkedin': baseline.get('linkedinUrl'),
        'qualification': baseline.get('highestQualification'),
        'skills': [s.strip() for s in (baseline.get('skillsRaw') or '').split(',') if s.strip()],
        'technology': [baseline.get('technologies')] if baseline.get('technologies') else [],
        'role': baseline.get('role') or baseline.get('technologiesRaw') or None,
        'total_experience': tot_exp,
        'location': baseline.get('currentLocation'),
    }

    resp_mock = MagicMock()
    resp_mock.status_code = 200
    resp_mock.json.return_value = {
        'candidates': [{
            'content': {'parts': [{'text': json.dumps(mock_parsed)}]},
            'finishReason': 'STOP',
        }]
    }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            return resp_mock

    src.ai.gemini.httpx.AsyncClient = MockAsyncClient

    with freeze_time('2026-11-02T12:00:00.000Z'):
        actual = run_coro(parse_resume_buffer(raw_text.encode('utf-8'), f"{input_id}.txt"))

    assert set(actual.keys()) == set(expected.keys()), (
        f"[{input_id}] key set mismatch: missing in actual={set(expected.keys()) - set(actual.keys())}, "
        f"extra in actual={set(actual.keys()) - set(expected.keys())}"
    )

    for field, exp_val in expected.items():
        act_val = actual[field]
        assert act_val == exp_val, f"[{input_id}] field '{field}' mismatch: expected {json.dumps(exp_val)}, got {json.dumps(act_val)}"


