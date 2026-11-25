import base64
from typing import TypedDict, Literal
from src.extractResumeText import _extract_docx_buffer, _extract_doc_stream

SUPPORTED = ['pdf', 'docx', 'doc', 'txt']


class ExtractedFileContent(TypedDict):
    type: Literal['pdf', 'text']
    data: str


def get_extension(filename: str) -> str:
    parts = filename.split('.')
    return parts[-1].lower() if len(parts) > 1 else ''


def is_supported_file(filename: str) -> bool:
    return get_extension(filename) in SUPPORTED


async def extract_file_content(
    buffer: bytes,
    filename: str,
) -> ExtractedFileContent:
    ext = get_extension(filename)

    if ext == 'pdf':
        return {
            'type': 'pdf',
            'data': base64.b64encode(buffer).decode('ascii'),
        }

    if ext == 'docx':
        text = _extract_docx_buffer(buffer)
        if not text.strip():
            raise RuntimeError('No text found. File may be image-based or scanned.')
        return {'type': 'text', 'data': text}

    if ext == 'doc':
        try:
            from tools.doc_extractor import extract_doc_text_via_node
            try:
                text = extract_doc_text_via_node(buffer)
            except Exception:
                text = _extract_doc_stream(buffer)
            if not text.strip():
                raise RuntimeError('No text found. File may be image-based or empty.')
            return {'type': 'text', 'data': text}
        except Exception as doc_err:
            raise RuntimeError(f"Failed to extract .doc file: {doc_err}")

    if ext == 'txt':
        return {
            'type': 'text',
            'data': buffer.decode('utf-8', errors='replace'),
        }

    raise RuntimeError(f"Unsupported file type: .{ext}")


getExtension = get_extension
isSupportedFile = is_supported_file
extractFileContent = extract_file_content
