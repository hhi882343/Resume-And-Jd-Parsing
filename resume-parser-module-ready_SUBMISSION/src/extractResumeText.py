"""
Plain text from resume bytes (PDF / DOC / DOCX), with OCR fallback for
scanned/image-only PDFs and image files.

Mirrors TypeScript src/extractResumeText.ts with exact path order, thresholds,
OCR options (--oem 1 --psm 3), safety limits, and error message mapping.
"""
import io
import os
import shutil
import tempfile
import asyncio
import zipfile
import subprocess
import xml.etree.ElementTree as ET
from typing import Optional, TypedDict, List
from PIL import Image
from src.jsRegex import js_trim, compile_re

try:
    import pymupdf
except ImportError as exc:
    raise ImportError("PyMuPDF (pymupdf) is required for PDF text extraction and OCR rendering. Install it via `pip install pymupdf`.") from exc

from tools.pdf_extractor import extract_pdf_text_via_node
from tools.doc_extractor import extract_doc_text_via_node
from tools.pdf_parse_extractor import extract_pdf_parse_text_via_node
Image.MAX_IMAGE_PIXELS = 60_000_000

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'}
OCR_MIN_TEXT_THRESHOLD = 40
OCR_MAX_PDF_PAGES = 5
MAX_PDF_NATIVE_PAGES = 50
OCR_TIMEOUT_SECONDS = 90.0
SUBPROCESS_TIMEOUT_SECONDS = 30.0


class ExtractResumeTextResult(TypedDict, total=False):
    text: str
    error: Optional[str]


def normalize_resume_text(raw: str) -> str:
    text = raw.replace('\r\n', '\n').replace('\r', '\n')
    text = compile_re(r'[ \t]+\n', 'g').sub('\n', text)
    text = compile_re(r'\n{3,}', 'g').sub('\n\n', text)
    return js_trim(text)


def is_likely_scanned_pdf(text: str) -> bool:
    t = normalize_resume_text(text)
    return len(t) < OCR_MIN_TEXT_THRESHOLD


def _ocr_image_sync(image_bytes: bytes) -> str:
    """OCR an image buffer using tesseract CLI with --oem 1 --psm 3 and local tessdata."""
    img = Image.open(io.BytesIO(image_bytes))
    # Enforce 60-million-pixel cap
    w, h = img.size
    if w * h > Image.MAX_IMAGE_PIXELS:
        raise ValueError(f"Image dimensions ({w}x{h} = {w*h} pixels) exceed 60-megapixel limit")

    tess_bin = shutil.which('tesseract')
    if not tess_bin and os.name == 'nt':
        default_win_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(default_win_path):
            tess_bin = default_win_path

    if not tess_bin:
        raise RuntimeError("Tesseract OCR executable not found on PATH. Install tesseract-ocr to enable OCR extraction.")

    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, 'image.png')
        img.save(img_path, format='PNG')

        cmd = [tess_bin, img_path, 'stdout', '--oem', '1', '--psm', '3']
        tessdata_dir = os.environ.get('TESSDATA_DIR')
        if not tessdata_dir:
            default_assets = os.path.join(os.path.dirname(__file__), '..', 'assets', 'tessdata')
            if os.path.exists(os.path.join(default_assets, 'eng.traineddata')):
                tessdata_dir = default_assets
        if tessdata_dir and os.path.exists(tessdata_dir):
            cmd.extend(['--tessdata-dir', os.path.abspath(tessdata_dir)])

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            shell=False,
        )
        if proc.returncode == 0:
            return normalize_resume_text(proc.stdout.decode('utf-8', errors='replace'))
        raise RuntimeError(f"Tesseract failed with exit code {proc.returncode}: {proc.stderr.decode('utf-8', errors='replace')}")


async def ocr_image_buffer(buffer: bytes) -> str:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    try:
        if loop is not None:
            text = await asyncio.wait_for(
                loop.run_in_executor(None, _ocr_image_sync, buffer),
                timeout=OCR_TIMEOUT_SECONDS
            )
        else:
            text = _ocr_image_sync(buffer)
        return text
    except Exception:
        return ''


def _render_pdf_pages_to_images(buffer: bytes) -> List[bytes]:
    doc = pymupdf.open(stream=buffer, filetype='pdf')
    if doc.needs_pass:
        raise ValueError("No password given")
    if len(doc) == 0:
        raise ValueError("Invalid PDF structure.")

    page_count = min(len(doc), OCR_MAX_PDF_PAGES)
    images: List[bytes] = []

    # scale 2.0 = 144 DPI (72 DPI * 2.0), exactly matching @napi-rs/canvas scale 2.0 in TS
    matrix = pymupdf.Matrix(2.0, 2.0)
    for i in range(page_count):
        page = doc[i]
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        images.append(pix.tobytes(output='png'))

    doc.close()
    return images


async def ocr_pdf_buffer(buffer: bytes) -> str:
    images = _render_pdf_pages_to_images(buffer)
    pages: List[str] = []
    for img in images:
        txt = await ocr_image_buffer(img)
        if txt:
            pages.append(txt)

    return normalize_resume_text('\n\n'.join(pages))


def _extract_text_with_pdfjs_stream_order(buffer: bytes) -> str:
    """Extract text from PDF preserving content stream order and line/space gap semantics.
    Matches pdfjs-dist getPage().getTextContent() in TS:
    - Traverses items in content-stream order (sort=False).
    - Checks vertical coordinate gap > 4 pt between lines to insert newline.
    - Adds space between adjacent non-whitespace items on the same line.
    """
    import pymupdf
    try:
        doc = pymupdf.open(stream=buffer, filetype='pdf')
    except Exception as exc:
        err_str = str(exc).lower()
        if 'password' in err_str:
            raise ValueError("No password given")
        raise ValueError("Invalid PDF structure.")

    if doc.needs_pass:
        raise ValueError("No password given")
    if len(doc) == 0:
        raise ValueError("Invalid PDF structure.")

    page_count = min(len(doc), MAX_PDF_NATIVE_PAGES)
    all_text = ''

    for i in range(page_count):
        page = doc[i]
        rawdict = page.get_text('rawdict')
        page_text = ''
        last_y: Optional[float] = None

        for b in rawdict.get('blocks', []):
            if b.get('type') != 0:
                continue
            for l in b.get('lines', []):
                for s in l.get('spans', []):
                    txt = ''.join(c.get('c', '') for c in s.get('chars', []))
                    if not txt:
                        continue
                    current_y = s.get('origin', (0, 0))[1]
                    if last_y is not None and abs(current_y - last_y) > 4:
                        page_text += '\n'
                    elif len(page_text) > 0 and not page_text.endswith('\n') and not page_text.endswith(' '):
                        page_text += ' '
                    page_text += txt
                    last_y = current_y

        all_text += page_text + '\n\n'

    doc.close()
    return normalize_resume_text(all_text)


def _extract_text_with_pdf_parse(buffer: bytes) -> str:
    """Fallback text extraction equivalent to Node's pdf-parse."""
    import pymupdf
    doc = pymupdf.open(stream=buffer, filetype='pdf')
    if doc.needs_pass:
        raise ValueError("No password given")
    if len(doc) == 0:
        raise ValueError("Invalid PDF structure.")

    page_count = min(len(doc), MAX_PDF_NATIVE_PAGES)
    parts = []
    for i in range(page_count):
        page = doc[i]
        parts.append(page.get_text('text'))
    doc.close()
    return normalize_resume_text(' '.join(parts))


def _extract_docx_buffer(buffer: bytes) -> str:
    """Extract plain text from DOCX using official python mammoth package matching Node mammoth."""
    import mammoth
    result = mammoth.extract_raw_text(io.BytesIO(buffer))
    return normalize_resume_text(result.value or '')


def _extract_doc_stream(buffer: bytes) -> str:
    """Extract plain text from legacy Word .doc format using Node word-extractor helper.
    Falls back to antiword/catdoc if present.
    """
    try:
        text = extract_doc_text_via_node(buffer)
        return normalize_resume_text(text)
    except Exception as e:
        # Fall back to antiword/catdoc CLI subprocess if available
        pass

    found_tool = False
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_path = os.path.join(tmpdir, 'resume.doc')
        with open(doc_path, 'wb') as f:
            f.write(buffer)

        for cmd in ['antiword', 'catdoc']:
            try:
                proc = subprocess.run(
                    [cmd, doc_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=SUBPROCESS_TIMEOUT_SECONDS,
                    shell=False
                )
                found_tool = True
                if proc.returncode == 0 and proc.stdout:
                    text = proc.stdout.decode('utf-8', errors='replace')
                    normalized = normalize_resume_text(text)
                    if normalized:
                        return normalized
            except FileNotFoundError:
                continue
            except (subprocess.TimeoutExpired, Exception):
                found_tool = True
                pass

    if not found_tool:
        raise RuntimeError("Neither 'antiword' nor 'catdoc' was found on PATH. Install antiword or catdoc to extract .doc files.")

    return ''


async def extract_plain_text_from_resume_buffer(
    buffer: bytes,
    filename: str,
) -> ExtractResumeTextResult:
    dot = filename.rfind('.')
    ext = filename[dot:].lower() if dot >= 0 else ''

    try:
        # Path 1: PDF
        if ext == '.pdf':
            # Pre-flight check for password or corruption (matches Node error strings)
            import pymupdf
            try:
                chk_doc = pymupdf.open(stream=buffer, filetype='pdf')
                if chk_doc.needs_pass:
                    chk_doc.close()
                    return {'text': '', 'error': 'No password given'}
                if len(chk_doc) == 0:
                    chk_doc.close()
                    return {'text': '', 'error': 'Invalid PDF structure.'}
                chk_doc.close()
            except Exception as exc:
                err_str = str(exc).lower()
                if 'password' in err_str:
                    return {'text': '', 'error': 'No password given'}
                return {'text': '', 'error': 'Invalid PDF structure.'}

            text = ''
            try:
                # Primary: verbatim pdf.js stream-order text via node helper
                text = normalize_resume_text(extract_pdf_text_via_node(buffer))
            except Exception as e:
                try:
                    text = _extract_text_with_pdfjs_stream_order(buffer)
                except Exception as inner_e:
                    err_msg = str(inner_e)
                    if err_msg in ("No password given", "Invalid PDF structure."):
                        return {'text': '', 'error': err_msg}
                    text = ''

            if is_likely_scanned_pdf(text):
                try:
                    parsed = normalize_resume_text(extract_pdf_parse_text_via_node(buffer))
                    if not is_likely_scanned_pdf(parsed):
                        text = parsed
                except Exception as e:
                    try:
                        parsed = _extract_text_with_pdf_parse(buffer)
                        if not is_likely_scanned_pdf(parsed):
                            text = parsed
                    except Exception as inner_e:
                        err_msg = str(inner_e)
                        if err_msg in ("No password given", "Invalid PDF structure."):
                            return {'text': '', 'error': err_msg}

            if not is_likely_scanned_pdf(text):
                return {'text': text}

            # OCR fallback for scanned/image-only PDFs
            try:
                ocr_text = await ocr_pdf_buffer(buffer)
                if not ocr_text:
                    return {
                        'text': '',
                        'error': 'No text found in this PDF after OCR.',
                    }
                return {'text': ocr_text}
            except Exception as e:
                err_msg = str(e)
                if err_msg in ("No password given", "Invalid PDF structure."):
                    return {'text': '', 'error': err_msg}
                return {
                    'text': '',
                    'error': 'Could not read text from this file.',
                }

        # Path 2: DOCX
        if ext == '.docx':
            try:
                text = _extract_docx_buffer(buffer)
            except Exception as exc:
                return {'text': '', 'error': f"Failed to read DOCX file: {exc}"}

            if not text:
                return {'text': '', 'error': 'No text could be read from this DOCX file.'}
            return {'text': text}

        # Path 3: DOC
        if ext == '.doc':
            text = _extract_doc_stream(buffer)
            if not text:
                return {'text': '', 'error': 'No text could be read from this DOC file.'}
            return {'text': text}

        # Path 4: Images
        if ext in IMAGE_EXTS:
            text = await ocr_image_buffer(buffer)
            if not text:
                return {'text': '', 'error': 'No text could be read from this image file.'}
            return {'text': text}

        # Path 5: Plain text / UTF-8 fallback
        raw_text = buffer.decode('utf-8', errors='replace')
        text = normalize_resume_text(raw_text)
        if not text:
            return {'text': '', 'error': 'Could not read text from this file.'}
        return {'text': text}

    except Exception as e:
        msg = str(e) if str(e) else 'Failed to read file'
        return {'text': '', 'error': msg}


# Aliases matching TS exports
extractPlainTextFromResumeBuffer = extract_plain_text_from_resume_buffer
normalizeResumeText = normalize_resume_text
isLikelyScannedPdf = is_likely_scanned_pdf
ocrPdfBuffer = ocr_pdf_buffer
ocrImageBuffer = ocr_image_buffer
