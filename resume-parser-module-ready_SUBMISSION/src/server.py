import os
from typing import Optional
from starlette.requests import Request
from starlette.responses import Response
from src.routes.resumeParserRouter import (
    handle_health,
    handle_parse,
    handle_parse_bulk,
    html_error_response,
    json_compact_response,
    RequestSizeLimitExceeded,
)
from src.metaforgeParser import is_metaforge_parser_available
from src.ai.config import config, get_ai_model_label, parse_port

# Streaming byte limiter with framing margin (outer envelope)
# Exact 15 MB per-file limit is enforced after multipart parsing in resumeParserRouter
STREAM_LIMIT_PARSE_BYTES = 16 * 1024 * 1024       # 16 MB (15 MB file + 1 MB multipart framing margin)
STREAM_LIMIT_BULK_BYTES = 80 * 1024 * 1024        # 80 MB (5 * 15 MB files + 5 MB multipart framing margin)


def get_byte_limit_for_path(path: str) -> Optional[int]:
    norm = path.lower().rstrip('/')
    if not norm:
        norm = '/'
    if norm in ('/parse', '/api/resume/parse'):
        return STREAM_LIMIT_PARSE_BYTES
    if norm in ('/parse/bulk', '/api/resume/parse/bulk'):
        return STREAM_LIMIT_BULK_BYTES
    return None


async def app_handler(scope, receive, send):
    if scope['type'] != 'http':
        return

    method = scope.get('method', 'GET')
    raw_path = scope.get('path', '/')

    # CORS Preflight
    if method == 'OPTIONS':
        request = Request(scope, receive=receive)
        req_headers = request.headers.get('access-control-request-headers')
        headers = {
            'access-control-allow-origin': '*',
            'access-control-allow-methods': 'GET,HEAD,PUT,PATCH,POST,DELETE',
            'vary': 'Access-Control-Request-Headers',
            'content-length': '0',
        }
        if req_headers:
            headers['access-control-allow-headers'] = req_headers
        response = Response(content=b'', status_code=204, headers=headers)
        await response(scope, receive, send)
        return

    # Streaming byte limit enforcement (Fix 1)
    limit = get_byte_limit_for_path(raw_path)
    if limit is not None:
        # 1. Fast-reject if Content-Length header exceeds limit
        cl_header = None
        for k, v in scope.get('headers', []):
            if k.lower() == b'content-length':
                try:
                    cl_header = int(v.decode('latin-1'))
                except (ValueError, TypeError):
                    pass
                break

        if cl_header is not None and cl_header > limit:
            response = json_compact_response({'success': False, 'message': 'File too large'}, 500)
            if 'access-control-allow-origin' not in response.headers:
                response.headers['access-control-allow-origin'] = '*'
            await response(scope, receive, send)
            return

        # 2. Wrap receive to enforce streaming byte count limit chunk-by-chunk without temp-file spooling
        bytes_streamed = 0
        original_receive = receive

        async def limited_receive():
            nonlocal bytes_streamed
            msg = await original_receive()
            if msg['type'] == 'http.request':
                chunk = msg.get('body', b'')
                bytes_streamed += len(chunk)
                if bytes_streamed > limit:
                    raise RequestSizeLimitExceeded()
            return msg

        receive = limited_receive

    request = Request(scope, receive=receive)

    # Normalize path: case-insensitive, strip trailing slashes
    norm_path = raw_path.lower().rstrip('/')
    if not norm_path:
        norm_path = '/'

    try:
        if norm_path in ('/health', '/api/resume/health'):
            response = await handle_health(request)
        elif norm_path in ('/parse', '/api/resume/parse'):
            response = await handle_parse(request)
        elif norm_path in ('/parse/bulk', '/api/resume/parse/bulk'):
            response = await handle_parse_bulk(request)
        else:
            if method == 'HEAD':
                response = Response(
                    content=b'',
                    status_code=404,
                    headers={
                        'content-type': 'text/html; charset=utf-8',
                        'access-control-allow-origin': '*',
                    },
                )
            else:
                response = html_error_response(f"Cannot {method} {raw_path}", 404)
    except RequestSizeLimitExceeded:
        response = json_compact_response({'success': False, 'message': 'File too large'}, 500)

    # Ensure Access-Control-Allow-Origin header is always present
    if 'access-control-allow-origin' not in response.headers:
        response.headers['access-control-allow-origin'] = '*'

    await response(scope, receive, send)


app = app_handler


if __name__ == '__main__':
    import uvicorn
    port = parse_port(os.environ.get('PORT'))
    ai_available = is_metaforge_parser_available()
    print("=======================================================")
    print(f"Resume Parser Service is running on http://localhost:{port}")
    print(f"AI Engine: {get_ai_model_label()} (Active)" if ai_available else "Local Deterministic Fallback")
    print(f"Health Check: http://localhost:{port}/health")
    print("Endpoints:")
    print(f"  POST http://localhost:{port}/api/resume/parse      (form-data field: \"resume\")")
    print(f"  POST http://localhost:{port}/api/resume/parse/bulk (form-data field: \"resumes\")")
    print("=======================================================")
    uvicorn.run("src.server:app", host="0.0.0.0", port=port, workers=1)
    print("=======================================================")
    print(f"Resume Parser Service is running on http://localhost:{port}")
    print(f"AI Engine: {get_ai_model_label()} (Active)" if ai_available else "Local Deterministic Fallback")
    print(f"Health Check: http://localhost:{port}/health")
    print("Endpoints:")
    print(f"  POST http://localhost:{port}/api/resume/parse      (form-data field: \"resume\")")
    print(f"  POST http://localhost:{port}/api/resume/parse/bulk (form-data field: \"resumes\")")
    print("=======================================================")
    uvicorn.run("src.server:app", host="0.0.0.0", port=port, workers=1)

