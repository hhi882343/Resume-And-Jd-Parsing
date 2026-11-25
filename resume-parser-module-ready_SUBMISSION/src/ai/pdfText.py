import os
import subprocess
from typing import Optional
from tools.pdf_parse_extractor import extract_pdf_parse_text_via_node
from tools.pdf_extractor import extract_pdf_text_via_node

async def extract_pdf_text(buffer: bytes) -> str:
    """
    Port of src/ai/pdfText.ts:
    1. Try pdf(buffer) (pdf-parse). If trimmed text.length > 40, return it.
    2. Fallback to pdfjs-dist getDocument / getTextContent, join(' ') per page, join('\\n') all pages.
    """
    try:
        text = extract_pdf_parse_text_via_node(buffer)
        trimmed = text.strip()
        if len(trimmed) > 40:
            return trimmed
    except Exception as err:
        pass

    try:
        # Fallback to pdf.js text
        text = extract_pdf_text_via_node(buffer)
        return text.strip()
    except Exception as err:
        return ""

extractPdfText = extract_pdf_text

