import json
import inspect
import re
from typing import Dict, Any, Tuple
from unittest.mock import patch
import pytest
from src.server import app
from src.metaforgeParser import reset_ai_parsing_suspended
import src.metaforgeParser
from src.ai.config import config
from src.clock import freeze_time


def run_coro(coro):
    stack = [coro]
    val, exc = None, None
    while stack:
        curr = stack[-1]
        try:
            res = curr.throw(exc) if exc else curr.send(val)
            exc = None
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


def call_app(method: str, path: str, headers: Dict[str, str] = None, body: bytes = b'') -> Tuple[int, Dict[str, str], bytes]:
    sent = []
    h = [(k.lower().encode('utf-8'), v.encode('utf-8')) for k, v in (headers or {}).items()]
    scope = {
        'type': 'http',
        'method': method,
        'path': path,
        'headers': h,
        'query_string': b'',
    }

    async def receive():
        return {'type': 'http.request', 'body': body, 'more_body': False}

    async def send(msg):
        sent.append(msg)

    async def runner():
        await app(scope, receive, send)

    run_coro(runner())

    start_msg = next((m for m in sent if m['type'] == 'http.response.start'), None)
    assert start_msg is not None, "ASGI app did not send http.response.start"
    status = start_msg['status']
    resp_headers = {k.decode('utf-8'): v.decode('utf-8') for k, v in start_msg.get('headers', [])}
    resp_body = b''.join(m.get('body', b'') for m in sent if m['type'] == 'http.response.body')
    return status, resp_headers, resp_body


def build_multipart(fields: list, boundary: str = '----WebKitFormBoundaryTest123') -> Tuple[str, bytes]:
    """
    fields: list of tuples:
      ('file', field_name, filename, mime_type, content_bytes)
      ('text', field_name, text_value)
    """
    lines = []
    b_boundary = boundary.encode('utf-8')
    chunks = []
    for item in fields:
        if item[0] == 'file':
            _, field_name, filename, mime_type, content_bytes = item
            header = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode('utf-8')
            chunks.append(header)
            chunks.append(content_bytes)
            chunks.append(b"\r\n")
        elif item[0] == 'text':
            _, field_name, val = item
            header = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'
                f"{val}\r\n"
            ).encode('utf-8')
            chunks.append(header)
    chunks.append(f"--{boundary}--\r\n".encode('utf-8'))
    return f"multipart/form-data; boundary={boundary}", b''.join(chunks)


@pytest.fixture(autouse=True)
def reset_config_and_state():
    orig_key = config.geminiApiKey
    orig_key2 = config.gemini_api_key
    config.geminiApiKey = ''
    config.gemini_api_key = ''
    reset_ai_parsing_suspended()
    yield
    config.geminiApiKey = orig_key
    config.gemini_api_key = orig_key2
    reset_ai_parsing_suspended()


# -----------------------------------------------------------------------------
# 5 Jest Tests Ported 1:1 from tests/resumeParserRouter.test.ts
# -----------------------------------------------------------------------------

def test_1_get_api_resume_health_returns_status():
    status, headers, body = call_app('GET', '/api/resume/health')
    assert status == 200
    res = json.loads(body.decode('utf-8'))
    assert res['status'] == 'ok'
    assert res['service'] == 'resume-parser-module'
    assert 'aiParserAvailable' in res
    assert 'mode' in res


def test_2_post_api_resume_parse_returns_400_if_no_file():
    status, headers, body = call_app('POST', '/api/resume/parse')
    assert status == 400
    res = json.loads(body.decode('utf-8'))
    assert res['success'] is False
    assert re.search(r'required', res['message'], re.I)


def test_3_post_api_resume_parse_parses_uploaded_text():
    resume_content = '\n'.join([
        'Ananya Sharma',
        'ananya.sharma@gmail.com',
        '+91 9876543210',
        'https://linkedin.com/in/ananyasharma',
        '',
        'Professional Summary',
        'Full Stack Developer with 4 years of experience building modern web apps.',
        '',
        'Technical Skills',
        'TypeScript, React, Node.js, PostgreSQL, Docker',
        '',
        'Education',
        'B.Tech in Computer Science from NIT Trichy (2018 - 2022)',
    ])

    content_type, body_bytes = build_multipart([
        ('file', 'resume', 'ananya_resume.txt', 'text/plain', resume_content.encode('utf-8'))
    ])

    with freeze_time('2026-11-02T12:00:00.000Z'):
        status, headers, body = call_app(
            'POST',
            '/api/resume/parse',
            headers={'content-type': content_type},
            body=body_bytes
        )

    assert status == 200
    res = json.loads(body.decode('utf-8'))
    assert res['success'] is True
    assert 'data' in res
    data = res['data']
    assert data['candidateName'] == 'Ananya Sharma'
    assert data['email'] == 'ananya.sharma@gmail.com'
    assert data['contactNumber'] == '+919876543210'
    assert 'TypeScript' in data['skillsRaw']
    assert 'React' in data['skillsRaw']
    assert 'Docker' in data['skillsRaw']
    assert data['technologiesRaw'] == 'Full Stack Developer'
    assert re.search(r'B\.?\s*Tech', data['highestQualification'], re.I)
    assert re.search(r'4\s*years', data['totalExperience'], re.I)


def test_4_post_api_resume_parse_bulk_returns_400_if_no_files():
    status, headers, body = call_app('POST', '/api/resume/parse/bulk')
    assert status == 400
    res = json.loads(body.decode('utf-8'))
    assert res['success'] is False


def test_5_post_api_resume_parse_bulk_parses_multiple_resumes():
    resume_a = '\n'.join([
        'Karthik Raju',
        'karthik@example.com',
        '+91 9123456780',
        '',
        'Professional Summary: DevOps Engineer with AWS experience.',
        '',
        'Skills: AWS, Terraform, Docker, Kubernetes',
    ])
    resume_b = '\n'.join([
        'Sneha Reddy',
        'sneha@example.com',
        '+91 9123456781',
        '',
        'Summary: Python Data Analyst specializing in SQL and Tableau.',
        '',
        'Key Skills: Python, SQL, Tableau, Pandas',
    ])

    content_type, body_bytes = build_multipart([
        ('file', 'resumes', 'karthik.txt', 'text/plain', resume_a.encode('utf-8')),
        ('file', 'resumes', 'sneha.txt', 'text/plain', resume_b.encode('utf-8')),
    ])

    with freeze_time('2026-11-02T12:00:00.000Z'):
        status, headers, body = call_app(
            'POST',
            '/api/resume/parse/bulk',
            headers={'content-type': content_type},
            body=body_bytes
        )

    assert status == 200
    res = json.loads(body.decode('utf-8'))
    assert res['success'] is True
    assert res['count'] == 2
    assert len(res['results']) == 2

    res_a, res_b = res['results']
    assert res_a['status'] == 'done'
    assert res_a['data']['candidateName'] == 'Karthik Raju'
    assert res_a['data']['technologiesRaw'] == 'DevOps Engineer'

    assert res_b['status'] == 'done'
    assert res_b['data']['candidateName'] == 'Sneha Reddy'
    assert res_b['data']['technologiesRaw'] == 'Python Data Analyst'


# -----------------------------------------------------------------------------
# Express Goldens Parity Tests (Matching express_goldens.json)
# -----------------------------------------------------------------------------

def test_express_goldens_case_insensitivity_and_trailing_slashes():
    # /HEALTH uppercase
    status, headers, body = call_app('GET', '/HEALTH')
    assert status == 200
    res = json.loads(body.decode('utf-8'))
    assert res['status'] == 'ok'

    # /health/ trailing slash
    status, headers, body = call_app('GET', '/health/')
    assert status == 200
    res = json.loads(body.decode('utf-8'))
    assert res['status'] == 'ok'

    # /API/resume/Parse mixed case
    status, headers, body = call_app('POST', '/API/resume/Parse')
    assert status == 400
    res = json.loads(body.decode('utf-8'))
    assert res['success'] is False
    assert res['message'] == 'Resume file is required under form field "resume"'


def test_express_goldens_cors_preflight():
    status, headers, body = call_app(
        'OPTIONS',
        '/api/resume/parse',
        headers={
            'access-control-request-headers': 'content-type',
            'access-control-request-method': 'POST',
        }
    )
    assert status == 204
    assert headers['access-control-allow-origin'] == '*'
    assert 'POST' in headers['access-control-allow-methods']
    assert headers['vary'] == 'Access-Control-Request-Headers'
    assert headers['access-control-allow-headers'] == 'content-type'
    assert body == b''


def test_express_goldens_health_with_key_and_after_suspension():
    config.geminiApiKey = 'test-key'
    config.gemini_api_key = 'test-key'
    reset_ai_parsing_suspended()

    status, headers, body = call_app('GET', '/health')
    assert status == 200
    res = json.loads(body.decode('utf-8'))
    assert res['aiParserAvailable'] is True
    assert res['mode'] == 'hybrid-ai-with-fallback'
    assert res['aiSuspendedNotice'] is None

    # Simulate 429 quota suspension
    src.metaforgeParser.ai_parsing_suspended = True
    src.metaforgeParser.ai_parsing_suspended_reason = (
        'Gemini API quota or rate limit reached \u2014 using keyword parser for remaining resumes.'
    )

    status, headers, body = call_app('GET', '/health')
    assert status == 200
    res = json.loads(body.decode('utf-8'))
    assert res['aiParserAvailable'] is True
    assert res['mode'] == 'local-deterministic'
    assert 'quota or rate limit reached' in res['aiSuspendedNotice']

    # Clean up
    reset_ai_parsing_suspended()
    config.geminiApiKey = ''
    config.gemini_api_key = ''


def test_express_goldens_multer_errors():
    # 1. wrong field name: "document" instead of "resume" -> MulterError: Unexpected field -> 500
    ct, body_bytes = build_multipart([
        ('file', 'document', 'test.txt', 'text/plain', b'some content')
    ])
    status, headers, body = call_app('POST', '/parse', headers={'content-type': ct}, body=body_bytes)
    assert status == 500
    assert b'Internal Server Error' in body

    # 2. two files to single parse -> MulterError: Unexpected field -> 500
    ct, body_bytes = build_multipart([
        ('file', 'resume', 'test1.txt', 'text/plain', b'Resume 1'),
        ('file', 'resume', 'test2.txt', 'text/plain', b'Resume 2'),
    ])
    status, headers, body = call_app('POST', '/parse', headers={'content-type': ct}, body=body_bytes)
    assert status == 500
    assert b'Internal Server Error' in body

    # 3. 0-byte file -> 500 "Could not read text from this file."
    ct, body_bytes = build_multipart([
        ('file', 'resume', 'empty.txt', 'text/plain', b'')
    ])
    status, headers, body = call_app('POST', '/parse', headers={'content-type': ct}, body=body_bytes)
    assert status == 500
    res = json.loads(body.decode('utf-8'))
    assert res['success'] is False
    assert res['message'] == 'Could not read text from this file.'

    # 4. unsupported extension -> 500
    ct, body_bytes = build_multipart([
        ('file', 'resume', 'resume.xyz', 'application/octet-stream', b'abc')
    ])
    status, headers, body = call_app('POST', '/parse', headers={'content-type': ct}, body=body_bytes)
    assert status == 500
    res = json.loads(body.decode('utf-8'))
    assert res['success'] is False
    assert 'not supported' in res['message']

    # 5. oversize file > 15MB -> 500
    large_buf = b'a' * (16 * 1024 * 1024)
    ct, body_bytes = build_multipart([
        ('file', 'resume', 'large.txt', 'text/plain', large_buf)
    ])
    status, headers, body = call_app('POST', '/parse', headers={'content-type': ct}, body=body_bytes)
    assert status == 500
    res = json.loads(body.decode('utf-8'))
    assert res['success'] is False
    assert res['message'] == 'File too large'

    # 6. bulk more than 5 files -> 400
    fields = [('file', 'resumes', f'f{i}.txt', 'text/plain', b'data') for i in range(6)]
    ct, body_bytes = build_multipart(fields)
    status, headers, body = call_app('POST', '/parse/bulk', headers={'content-type': ct}, body=body_bytes)
    assert status == 400
    res = json.loads(body.decode('utf-8'))
    assert res['success'] is False
    assert res['message'] == 'Maximum 5 resumes allowed per batch upload'


def test_express_goldens_head_and_404_and_invalid_json():
    # HEAD /health -> 200, empty body
    status, headers, body = call_app('HEAD', '/health')
    assert status == 200
    assert body == b''
    assert headers['content-type'] == 'application/json; charset=utf-8'

    # HEAD /parse -> 404, empty body
    status, headers, body = call_app('HEAD', '/parse')
    assert status == 404
    assert body == b''

    # GET /unknown/path -> 404 HTML
    status, headers, body = call_app('GET', '/unknown/path')
    assert status == 404
    assert b'Cannot GET /unknown/path' in body

    # Invalid JSON body -> 400 HTML Bad Request (Production format, no stack trace)
    status, headers, body = call_app(
        'POST',
        '/parse',
        headers={'content-type': 'application/json'},
        body=b'{ "key": invalid_json }'
    )
    assert status == 400
    assert b'Bad Request' in body
    assert b'SyntaxError' not in body  # Production format: no stack trace leaked


def test_streaming_byte_limit_100mb_upload_rejected():
    """Test 100 MB upload rejection by ASGI streaming byte limit middleware.
    1. Verifies immediate rejection with 500 JSON 'File too large'.
    2. Verifies rejection happens without temp-file spooling.
    3. Verifies both Content-Length pre-flight rejection and chunked streaming byte limit rejection.
    """
    # Case A: 100 MB request with Content-Length header
    status, headers, body = call_app(
        'POST',
        '/api/resume/parse',
        headers={
            'content-type': 'multipart/form-data; boundary=----WebKitFormBoundaryTest123',
            'content-length': str(100 * 1024 * 1024),
        },
        body=b''  # Zero bytes received because rejected before receiving body
    )
    assert status == 500
    res = json.loads(body.decode('utf-8'))
    assert res['success'] is False
    assert res['message'] == 'File too large'

    # Case B: Streaming chunks exceeding 15 MB without Content-Length
    sent = []
    scope = {
        'type': 'http',
        'method': 'POST',
        'path': '/parse',
        'headers': [(b'content-type', b'multipart/form-data; boundary=----WebKitFormBoundaryTest123')],
        'query_string': b'',
    }

    boundary = '----WebKitFormBoundaryTest123'
    part_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="resume"; filename="large.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
    ).encode('utf-8')

    # Stream 1 MB chunks; once chunk 16 arrives (> 15 MB), limited_receive raises RequestSizeLimitExceeded
    chunk_1mb = b'a' * (1024 * 1024)
    chunks_sent = 0

    async def streaming_receive():
        nonlocal chunks_sent
        chunks_sent += 1
        if chunks_sent == 1:
            body = part_header + chunk_1mb
        else:
            body = chunk_1mb
        return {'type': 'http.request', 'body': body, 'more_body': chunks_sent < 100}

    async def capturing_send(msg):
        sent.append(msg)

    async def runner():
        await app(scope, streaming_receive, capturing_send)

    run_coro(runner())

    start_msg = next((m for m in sent if m['type'] == 'http.response.start'), None)
    assert start_msg is not None
    assert start_msg['status'] == 500
    resp_body = b''.join(m.get('body', b'') for m in sent if m['type'] == 'http.response.body')
    res = json.loads(resp_body.decode('utf-8'))
    assert res['success'] is False
    assert res['message'] == 'File too large'
    # Middleware stopped stream after 16 MB, far before 100 MB, with 0 temp-file spooling
    assert chunks_sent <= 17


def test_express_timeout_socket_destruction():
    """Test what Express/ASGI does when request timeout expires.
    Artificially short timeout fires and drops connection without sending response,
    matching Node.js socket.destroy() behavior.
    """
    import src.routes.resumeParserRouter as rpr

    ct, body_bytes = build_multipart([
        ('file', 'resume', 'test.txt', 'text/plain', b'Some resume')
    ])

    # Simulate timeout event during buffer parsing
    async def timeout_parse(*args, **kwargs):
        raise TimeoutError("Request timed out")

    with patch('src.routes.resumeParserRouter.parse_resume_buffer', timeout_parse):
        sent = []
        scope = {
            'type': 'http',
            'method': 'POST',
            'path': '/parse',
            'headers': [(b'content-type', ct.encode('utf-8'))],
            'query_string': b'',
        }

        async def receive():
            return {'type': 'http.request', 'body': body_bytes, 'more_body': False}

        async def send(msg):
            sent.append(msg)

        # TimeoutError bubbles out to ASGI server, terminating socket with 0 response headers
        with pytest.raises(TimeoutError):
            run_coro(app(scope, receive, send))

        # Socket was destroyed with 0 response headers sent, matching Node.js socket.destroy()
        assert not any(m['type'] == 'http.response.start' for m in sent)


def test_port_parsing_semantics():
    from src.ai.config import parse_port
    assert parse_port('') == 3001
    assert parse_port('0') == 3001
    assert parse_port('0.0') == 3001
    assert parse_port('invalid') == 3001
    assert parse_port(None) == 3001
    assert parse_port('   ') == 3001
    assert parse_port('8080') == 8080
    assert parse_port('3000') == 3000


def test_file_size_boundary_14_9mb_and_15_1mb():
    """Test 14.9 MB and 15.1 MB files against the 15 MB boundary.
    - 14.9 MB file (< 15 MB) is accepted and processed (200 OK).
    - 15.1 MB file (> 15 MB) is rejected with 500 JSON 'File too large' after multipart parsing.
    """
    from unittest.mock import AsyncMock

    mock_parsed = {
        'candidateName': 'John Doe',
        'email': None,
        'phone': None,
        'skills': [],
        'experienceYears': 0,
        'education': [],
        'workExperience': [],
        'certifications': [],
        'languages': [],
        'currentLocation': None,
    }

    # 1. 14.9 MB file (15,623,782 bytes) -> under 15 MB limit -> Accepted (200)
    size_14_9 = int(14.9 * 1024 * 1024)
    buf_14_9 = b'x' * size_14_9
    ct, body_bytes_14_9 = build_multipart([('file', 'resume', 'large_ok.txt', 'text/plain', buf_14_9)])

    with patch('src.routes.resumeParserRouter.parse_resume_buffer', new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = mock_parsed
        status, headers, body = call_app('POST', '/parse', headers={'content-type': ct}, body=body_bytes_14_9)
        assert status == 200
        res = json.loads(body.decode('utf-8'))
        assert res['success'] is True
        assert mock_parse.called

    # 2. 15.1 MB file (15,833,497 bytes) -> over 15 MB limit -> Rejected (500)
    size_15_1 = int(15.1 * 1024 * 1024)
    buf_15_1 = b'y' * size_15_1
    ct, body_bytes_15_1 = build_multipart([('file', 'resume', 'large_fail.txt', 'text/plain', buf_15_1)])

    with patch('src.routes.resumeParserRouter.parse_resume_buffer', new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = mock_parsed
        status, headers, body = call_app('POST', '/parse', headers={'content-type': ct}, body=body_bytes_15_1)
        assert status == 500
        res = json.loads(body.decode('utf-8'))
        assert res['success'] is False
        assert res['message'] == 'File too large'
        # Crucial: parse_resume_buffer was NOT invoked because file was rejected at size check
        assert not mock_parse.called


def test_http_goldens_file_equivalence():
    import os
    from tests.parity_paths import get_public_parity_dir
    goldens_path = os.path.join(get_public_parity_dir(), 'golden', 'http_goldens.json')
    with open(goldens_path, 'r', encoding='utf-8') as f:
        goldens = json.load(f)

    # 1. cors_headers
    status, headers, body = call_app('GET', '/health')
    assert headers['access-control-allow-origin'] == goldens['cors_headers']['access-control-allow-origin']

    # 2. health_without_key
    config.geminiApiKey = ''
    config.gemini_api_key = ''
    reset_ai_parsing_suspended()
    status, headers, body = call_app('GET', '/health')
    assert status == goldens['health_without_key']['statusCode']
    assert json.loads(body.decode('utf-8')) == goldens['health_without_key']['body']

    # 3. health_with_key
    config.geminiApiKey = 'test-key'
    config.gemini_api_key = 'test-key'
    reset_ai_parsing_suspended()
    status, headers, body = call_app('GET', '/health')
    assert status == goldens['health_with_key']['statusCode']
    assert json.loads(body.decode('utf-8')) == goldens['health_with_key']['body']

    # 4. api_resume_health
    status, headers, body = call_app('GET', '/api/resume/health')
    assert status == goldens['api_resume_health']['statusCode']
    assert json.loads(body.decode('utf-8')) == goldens['api_resume_health']['body']

    # 5. parse_missing_file
    status, headers, body = call_app('POST', '/parse')
    assert status == goldens['parse_missing_file']['statusCode']
    assert json.loads(body.decode('utf-8')) == goldens['parse_missing_file']['body']

    # 6. parse_oversize_file
    large_buf = b'a' * (16 * 1024 * 1024)
    ct, body_bytes = build_multipart([('file', 'resume', 'large.txt', 'text/plain', large_buf)])
    status, headers, body = call_app('POST', '/parse', headers={'content-type': ct}, body=body_bytes)
    assert status == goldens['parse_oversize_file']['statusCode']
    assert json.loads(body.decode('utf-8')) == goldens['parse_oversize_file']['body']

    # 7. parse_unsupported_extension
    ct, body_bytes = build_multipart([('file', 'resume', 'resume.xyz', 'application/octet-stream', b'abc')])
    status, headers, body = call_app('POST', '/parse', headers={'content-type': ct}, body=body_bytes)
    assert status == goldens['parse_unsupported_extension']['statusCode']
    assert json.loads(body.decode('utf-8')) == goldens['parse_unsupported_extension']['body']

    # 8. bulk_more_than_5_files
    fields = [('file', 'resumes', f'f{i}.txt', 'text/plain', b'data') for i in range(6)]
    ct, body_bytes = build_multipart(fields)
    status, headers, body = call_app('POST', '/parse/bulk', headers={'content-type': ct}, body=body_bytes)
    assert status == goldens['bulk_more_than_5_files']['statusCode']
    assert json.loads(body.decode('utf-8')) == goldens['bulk_more_than_5_files']['body']

    # 9. parse_success with sample_resume.txt
    config.geminiApiKey = ''
    config.gemini_api_key = ''
    sample_path = os.path.join(os.path.dirname(__file__), '..', 'sample_resume.txt')
    with open(sample_path, 'r', encoding='utf-8') as f:
        sample_text = f.read()

    ct, body_bytes = build_multipart([('file', 'resume', 'sample_resume.txt', 'text/plain', sample_text.encode('utf-8'))])
    with freeze_time('2026-11-02T12:00:00.000Z'):
        status, headers, body = call_app('POST', '/parse', headers={'content-type': ct}, body=body_bytes)
    assert status == goldens['parse_success']['statusCode']
    assert json.loads(body.decode('utf-8')) == goldens['parse_success']['body']

    # 10. api_resume_parse_success
    with freeze_time('2026-11-02T12:00:00.000Z'):
        status, headers, body = call_app('POST', '/api/resume/parse', headers={'content-type': ct}, body=body_bytes)
    assert status == goldens['api_resume_parse_success']['statusCode']
    assert json.loads(body.decode('utf-8')) == goldens['api_resume_parse_success']['body']

