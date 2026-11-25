import os
import json
import base64
from unittest.mock import MagicMock
import pytest
from src.metaforgeParser import parse_resume_buffer, reset_ai_parsing_suspended
from src.ai.config import config
from src.clock import freeze_time
import src.ai.gemini
from tests.test_path3_goldens_parity import run_coro
from tests.parity_paths import get_private_parity_dir

PRIV_PARITY = get_private_parity_dir()
CORPUS_GOLDEN_PATH = os.path.join(PRIV_PARITY, "golden", "corpus_path3_recorded_goldens.json")
DOCX_DIR = os.path.join(PRIV_PARITY, "corpus")
DOC_DIR = os.path.join(PRIV_PARITY, "doc_corpus")
PDF_DIR = os.path.join(PRIV_PARITY, "converted_pdfs")

@pytest.fixture(autouse=True)
def setup_env():
    config.geminiApiKey = 'mock-key-for-golden-generation'
    config.gemini_api_key = 'mock-key-for-golden-generation'
    reset_ai_parsing_suspended()


def get_mock_client():
    mock_ai_response = {
        'candidates': [{
            'content': {
                'parts': [{
                    'text': json.dumps({
                        'full_name': 'Corpus Candidate',
                        'email': 'candidate@example.com',
                        'contact': '+1234567890',
                        'qualification': 'Bachelor of Science',
                        'skills': ['Python', 'TypeScript', 'Node.js'],
                        'technology': ['React'],
                        'role': 'Software Engineer',
                        'total_experience': '5 years',
                        'location': 'New York'
                    })
                }]
            },
            'finishReason': 'STOP'
        }]
    }

    resp_mock = MagicMock()
    resp_mock.status_code = 200
    resp_mock.json.return_value = mock_ai_response

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            return resp_mock

    return MockAsyncClient


@pytest.mark.skipif(not os.path.exists(CORPUS_GOLDEN_PATH), reason="Corpus Path 3 goldens missing")
def test_corpus_path3_30_files_parity():
    """Verify parse_resume_buffer (Path 3) on 10 DOCX, 10 DOC, 10 PDF corpus files with mock Gemini."""
    with open(CORPUS_GOLDEN_PATH, "r", encoding="utf-8") as f:
        goldens = json.load(f)

    src.ai.gemini.httpx.AsyncClient = get_mock_client()

    keys = [
        'candidateName', 'email', 'contactNumber', 'linkedinUrl', 'highestQualification',
        'skillsRaw', 'technologiesRaw', 'technologies', 'totalExperience', 'relevantExperience',
        'currentEmployer', 'currentLocation', 'location', 'sourceFile', 'parser', 'role'
    ]

    for filename, expected in goldens.items():
        if filename.endswith(".docx"):
            filepath = os.path.join(DOCX_DIR, filename)
        elif filename.endswith(".doc"):
            filepath = os.path.join(DOC_DIR, filename)
        elif filename.endswith(".pdf"):
            filepath = os.path.join(PDF_DIR, filename)
        else:
            continue

        with open(filepath, "rb") as f:
            buf = f.read()

        with freeze_time('2026-11-02T12:00:00.000Z'):
            actual = run_coro(parse_resume_buffer(buf, filename))

        for k in keys:
            assert actual.get(k) == expected.get(k), f"[{filename}] mismatch in {k}: got {actual.get(k)} != exp {expected.get(k)}"
