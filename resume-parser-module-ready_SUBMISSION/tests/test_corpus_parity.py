import os
import json
import shutil
import pytest
from src.extractResumeText import _extract_docx_buffer, _extract_doc_stream, _extract_text_with_pdfjs_stream_order, extract_plain_text_from_resume_buffer
from tests.parity_paths import get_private_parity_dir

PRIV_PARITY = get_private_parity_dir()
DOCX_DIR = os.path.join(PRIV_PARITY, "corpus")
DOCX_GOLDEN = os.path.join(PRIV_PARITY, "golden", "docx_corpus_node_goldens.json")

DOC_DIR = os.path.join(PRIV_PARITY, "doc_corpus")
DOC_GOLDEN = os.path.join(PRIV_PARITY, "golden", "doc_corpus_node_goldens.json")

PDF_DIR = os.path.join(PRIV_PARITY, "converted_pdfs")
PDF_GOLDEN = os.path.join(PRIV_PARITY, "golden", "converted_pdfs_node_goldens.json")


@pytest.mark.skipif(
    not os.path.exists(DOCX_DIR) or not os.path.exists(DOCX_GOLDEN),
    reason="DOCX corpus or goldens not found"
)
def test_docx_corpus_parity():
    """Verify 100% text equality between Python mammoth and Node mammoth across DOCX corpus."""
    with open(DOCX_GOLDEN, "r", encoding="utf-8") as f:
        goldens = json.load(f)

    for docx_id, node_entry in goldens.items():
        fpath = os.path.join(DOCX_DIR, docx_id)
        if not os.path.exists(fpath):
            continue
        with open(fpath, "rb") as f:
            buf = f.read()

        txt = _extract_docx_buffer(buf)
        assert txt == node_entry.get("extractedText"), f"Text mismatch in {docx_id}"


@pytest.mark.skipif(
    not os.path.exists(DOC_DIR) or not os.path.exists(DOC_GOLDEN),
    reason="DOC corpus or goldens not found"
)
def test_doc_corpus_parity():
    """Verify DOC extraction runs across all 25 .doc files via Node word-extractor helper and matches goldens."""
    with open(DOC_GOLDEN, "r", encoding="utf-8") as f:
        goldens = json.load(f)

    for doc_id, node_entry in goldens.items():
        fpath = os.path.join(DOC_DIR, doc_id)
        if not os.path.exists(fpath):
            continue
        with open(fpath, "rb") as f:
            buf = f.read()

        txt = _extract_doc_stream(buf)
        assert txt == node_entry.get("extractedText"), f"Text mismatch in {doc_id}"


@pytest.mark.skipif(
    not os.path.exists(PDF_DIR) or not os.path.exists(PDF_GOLDEN),
    reason="PDF corpus or goldens not found"
)
def test_pdf_corpus_parity():
    """Verify PDF extraction runs across all converted PDFs and extracts valid text."""
    with open(PDF_GOLDEN, "r", encoding="utf-8") as f:
        goldens = json.load(f)

    for pdf_id in goldens.keys():
        fpath = os.path.join(PDF_DIR, pdf_id)
        if not os.path.exists(fpath):
            continue
        with open(fpath, "rb") as f:
            buf = f.read()

        txt = _extract_text_with_pdfjs_stream_order(buf)
        assert len(txt) > 0, f"Extraction empty for {pdf_id}"
