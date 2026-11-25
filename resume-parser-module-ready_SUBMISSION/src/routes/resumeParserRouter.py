import os
import json
import asyncio
from typing import Any, Dict, List, Optional
import starlette.formparsers as formparsers
from starlette.requests import Request
from starlette.responses import Response
from src.metaforgeParser import (
    parse_resume_buffer,
    parse_resume_buffers_bulk,
    is_metaforge_parser_available,
    get_ai_parsing_suspended_reason,
)

# Match Express multer.memoryStorage() behavior: up to 50MB held in memory without disk writes
formparsers.MultiPartParser.spool_max_size = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    '.pdf',
    '.doc',
    '.docx',
    '.txt',
    '.png',
    '.jpg',
    '.jpeg',
    '.webp',
    '.bmp',
    '.tif',
    '.tiff',
}

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB
TIMEOUT_PARSE_SECONDS = float(os.environ.get("TIMEOUT_PARSE_SECONDS", 5 * 60))     # 5 minutes
TIMEOUT_BULK_SECONDS = float(os.environ.get("TIMEOUT_BULK_SECONDS", 10 * 60))     # 10 minutes


class RequestSizeLimitExceeded(Exception):
    def __init__(self, message: str = "File too large"):
        super().__init__(message)


def json_compact_response(data: Any, status_code: int = 200, headers: Optional[Dict[str, str]] = None) -> Response:
    body = json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    resp_headers = {
        'content-type': 'application/json; charset=utf-8',
        'access-control-allow-origin': '*',
    }
    if headers:
        resp_headers.update(headers)
    return Response(content=body, status_code=status_code, headers=resp_headers)


def html_error_response(message: str, status_code: int = 500) -> Response:
    """Production Express HTML error responses: no internal stack traces leaked.
    - 404: Cannot {METHOD} {PATH}
    - 400: Bad Request
    - 500: Internal Server Error
    """
    if status_code == 404:
        display_text = message
    elif status_code == 400:
        display_text = "Bad Request"
    elif status_code == 500:
        display_text = "Internal Server Error"
    else:
        display_text = message

    body = (
        f"<!DOCTYPE html>\n"
        f"<html lang=\"en\">\n"
        f"<head>\n"
        f"<meta charset=\"utf-8\">\n"
        f"<title>Error</title>\n"
        f"</head>\n"
        f"<body>\n"
        f"<pre>{display_text}</pre>\n"
        f"</body>\n"
        f"</html>\n"
    ).encode('utf-8')
    return Response(
        content=body,
        status_code=status_code,
        headers={
            'content-type': 'text/html; charset=utf-8',
            'access-control-allow-origin': '*',
        },
    )


async def handle_health(request: Request) -> Response:
    if request.method not in ('GET', 'HEAD'):
        return html_error_response(f"Cannot {request.method} {request.url.path}", 404)

    ai_available = is_metaforge_parser_available()
    suspended_reason = get_ai_parsing_suspended_reason()
    mode = 'hybrid-ai-with-fallback' if (ai_available and not suspended_reason) else 'local-deterministic'

    data = {
        'status': 'ok',
        'service': 'resume-parser-module',
        'aiParserAvailable': ai_available,
        'aiSuspendedNotice': suspended_reason,
        'mode': mode,
    }

    if request.method == 'HEAD':
        return Response(
            content=b'',
            status_code=200,
            headers={
                'content-type': 'application/json; charset=utf-8',
                'access-control-allow-origin': '*',
            },
        )

    return json_compact_response(data, 200)


async def handle_parse(request: Request) -> Response:
    if request.method != 'POST':
        if request.method == 'HEAD':
            return Response(
                content=b'',
                status_code=404,
                headers={
                    'content-type': 'text/html; charset=utf-8',
                    'access-control-allow-origin': '*',
                },
            )
        return html_error_response(f"Cannot {request.method} {request.url.path}", 404)

    content_type = request.headers.get('content-type', '').lower()

    # Check for invalid json body
    if 'application/json' in content_type:
        raw_body = await request.body()
        try:
            json.loads(raw_body)
        except Exception as e:
            return html_error_response(f"SyntaxError: {str(e)}", 400)
        return json_compact_response({
            'success': False,
            'message': 'Resume file is required under form field "resume"',
        }, 400)

    # Check multipart
    if not content_type.startswith('multipart/form-data'):
        return json_compact_response({
            'success': False,
            'message': 'Resume file is required under form field "resume"',
        }, 400)

    try:
        form = await request.form(max_part_size=50 * 1024 * 1024)
    except RequestSizeLimitExceeded:
        return json_compact_response({
            'success': False,
            'message': 'File too large',
        }, 500)
    except Exception as exc:
        if 'size' in str(exc).lower():
            return json_compact_response({
                'success': False,
                'message': 'File too large',
            }, 500)
        return html_error_response("MulterError: Malformed multipart", 500)

    # Inspect uploaded files
    uploaded_files: List[Any] = []
    has_unexpected_fields = False

    for key, value in form.multi_items():
        if hasattr(value, 'filename') and hasattr(value, 'read'):
            if key != 'resume':
                has_unexpected_fields = True
            uploaded_files.append((key, value))

    if has_unexpected_fields:
        return html_error_response("MulterError: Unexpected field", 500)

    if len(uploaded_files) > 1:
        return html_error_response("MulterError: Unexpected field", 500)

    if not uploaded_files:
        return json_compact_response({
            'success': False,
            'message': 'Resume file is required under form field "resume"',
        }, 400)

    field_name, file_item = uploaded_files[0]
    filename = file_item.filename or 'resume.pdf'
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return json_compact_response({
            'success': False,
            'message': f"File format {ext} is not supported. Supported: PDF, DOCX, DOC, TXT, and common image formats.",
        }, 500)

    file_bytes = await file_item.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        return json_compact_response({
            'success': False,
            'message': 'File too large',
        }, 500)

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            async with asyncio.timeout(TIMEOUT_PARSE_SECONDS):
                parsed = await parse_resume_buffer(file_bytes, filename)
        else:
            parsed = await parse_resume_buffer(file_bytes, filename)

        return json_compact_response({
            'success': True,
            'message': 'Resume parsed successfully',
            'data': parsed,
        }, 200)
    except TimeoutError:
        raise
    except Exception as err:
        return json_compact_response({
            'success': False,
            'message': str(err) if str(err) else 'Failed to parse resume',
        }, 500)


async def handle_parse_bulk(request: Request) -> Response:
    if request.method != 'POST':
        if request.method == 'HEAD':
            return Response(
                content=b'',
                status_code=404,
                headers={
                    'content-type': 'text/html; charset=utf-8',
                    'access-control-allow-origin': '*',
                },
            )
        return html_error_response(f"Cannot {request.method} {request.url.path}", 404)

    content_type = request.headers.get('content-type', '').lower()
    if not content_type.startswith('multipart/form-data'):
        return json_compact_response({
            'success': False,
            'message': 'At least one resume file is required under form field "resumes"',
        }, 400)

    try:
        form = await request.form(max_part_size=50 * 1024 * 1024)
    except RequestSizeLimitExceeded:
        return json_compact_response({
            'success': False,
            'message': 'File too large',
        }, 500)
    except Exception as exc:
        if 'size' in str(exc).lower():
            return json_compact_response({
                'success': False,
                'message': 'File too large',
            }, 500)
        return html_error_response("MulterError: Malformed multipart", 500)

    uploaded_files: List[Any] = []
    has_unexpected_fields = False

    for key, value in form.multi_items():
        if hasattr(value, 'filename') and hasattr(value, 'read'):
            if key != 'resumes':
                has_unexpected_fields = True
            uploaded_files.append((key, value))

    if has_unexpected_fields:
        return html_error_response("MulterError: Unexpected field", 500)

    if not uploaded_files:
        return json_compact_response({
            'success': False,
            'message': 'At least one resume file is required under form field "resumes"',
        }, 400)

    if len(uploaded_files) > 5:
        return json_compact_response({
            'success': False,
            'message': 'Maximum 5 resumes allowed per batch upload',
        }, 400)

    inputs_to_parse = []
    file_metadata = []

    for _, file_item in uploaded_files:
        filename = file_item.filename or 'resume.pdf'
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            file_metadata.append({
                'type': 'error',
                'item': {
                    'sourceFile': filename,
                    'status': 'error',
                    'error': f"File format {ext} is not supported. Supported: PDF, DOCX, DOC, TXT, and common image formats.",
                }
            })
            continue

        file_bytes = await file_item.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            file_metadata.append({
                'type': 'error',
                'item': {
                    'sourceFile': filename,
                    'status': 'error',
                    'error': 'File too large',
                }
            })
            continue

        idx = len(inputs_to_parse)
        inputs_to_parse.append({'buffer': file_bytes, 'filename': filename})
        file_metadata.append({'type': 'parse', 'index': idx})

    try:
        if inputs_to_parse:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                async with asyncio.timeout(TIMEOUT_BULK_SECONDS):
                    parsed_results = await parse_resume_buffers_bulk(inputs_to_parse)
            else:
                parsed_results = await parse_resume_buffers_bulk(inputs_to_parse)
        else:
            parsed_results = []

        results = []
        for meta in file_metadata:
            if meta['type'] == 'error':
                results.append(meta['item'])
            else:
                results.append(parsed_results[meta['index']])

        used_legacy = any(r.get('status') == 'done' and r.get('data', {}).get('parser') == 'legacy' for r in results)
        ai_notice = get_ai_parsing_suspended_reason()
        parser_label = 'metaforge' if (is_metaforge_parser_available() and not used_legacy and not ai_notice) else 'legacy'

        return json_compact_response({
            'success': True,
            'message': 'Bulk resume parse completed',
            'count': len(results),
            'parser': parser_label,
            'notice': ai_notice,
            'results': results,
        }, 200)
    except TimeoutError:
        raise
    except Exception as err:
        return json_compact_response({
            'success': False,
            'message': str(err) if str(err) else 'Bulk resume parse failed',
        }, 500)
