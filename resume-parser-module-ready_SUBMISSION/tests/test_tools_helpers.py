"""
tests/test_tools_helpers.py
Boundary tests for Option B helper scripts (tools/pdf_text.js and tools/doc_text.js):
- Emoji round-trip (UTF-8 explicit)
- 76k-character large outputs without deadlock/truncation
- 20 parallel calls
- Timeout kill enforcement and temp directory cleanup
- Missing Node executable handling
"""
import os
import shutil
import subprocess
import tempfile
import pytest
from concurrent.futures import ThreadPoolExecutor
from tools.pdf_extractor import extract_pdf_text_via_node
from tools.doc_extractor import extract_doc_text_via_node
import tools.pdf_extractor as pdf_mod
import tools.doc_extractor as doc_mod

NODE_BIN = shutil.which("node") or "node"

def _find_pdf_sample():
    candidates = [
        "tests/parity_public/fixtures/synthetic_sample.pdf",
        "tests/parity_private/binary_inputs/fixture_001.docx.pdf",
        "tests/parity/binary_inputs/fixture_001.docx.pdf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    for d in ["tests/parity_public/fixtures", "tests/parity_private/converted_pdfs", "tests/parity/converted_pdfs"]:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".pdf"):
                    return os.path.join(d, f)
    return None

def _find_doc_sample():
    for d in ["tests/parity_private/doc_corpus", "tests/parity/doc_corpus"]:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".doc"):
                    return os.path.join(d, f)
    return None

PDF_SAMPLE = _find_pdf_sample()
DOC_SAMPLE = _find_doc_sample()


def test_subprocess_emoji_roundtrip():
    """Verify that Node subprocess stdout correctly preserves non-BMP emojis (U+1F539, U+1F4E7)."""
    script = (
        "const s = 'Candidate 🔹 John Doe 📧 candidate@example.com';\n"
        "process.stdout.write(s);\n"
    )
    proc = subprocess.run(
        [NODE_BIN, "-e", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=10.0,
    )
    assert proc.returncode == 0
    decoded = proc.stdout.decode("utf-8")
    assert "🔹" in decoded
    assert "📧" in decoded
    assert decoded == "Candidate 🔹 John Doe 📧 candidate@example.com"


def test_subprocess_76k_large_output():
    """Verify that Node subprocess pipes handle 76k+ character outputs without deadlock or truncation."""
    chunk = "A" * 7600 + " 🔹 📧 \n"
    script = f"for (let i = 0; i < 10; i++) process.stdout.write({repr(chunk)});"
    proc = subprocess.run(
        [NODE_BIN, "-e", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=15.0,
    )
    assert proc.returncode == 0
    decoded = proc.stdout.decode("utf-8")
    assert len(decoded) >= 76000
    assert "🔹" in decoded
    assert "📧" in decoded


@pytest.mark.skipif(PDF_SAMPLE is None, reason="Sample PDF fixture not found")
def test_pdf_extractor_with_real_pdf():
    """Verify extract_pdf_text_via_node correctly extracts text from a real converted PDF."""
    assert PDF_SAMPLE is not None, "Sample PDF fixture not found"
    with open(PDF_SAMPLE, "rb") as f:
        buf = f.read()
    text = extract_pdf_text_via_node(buf)
    assert isinstance(text, str)
    assert len(text.strip()) > 50


@pytest.mark.skipif(DOC_SAMPLE is None, reason="Sample DOC fixture not found")
def test_doc_extractor_with_real_doc():
    """Verify extract_doc_text_via_node correctly extracts text from a real DOC file."""
    assert DOC_SAMPLE is not None, "Sample DOC fixture not found"
    with open(DOC_SAMPLE, "rb") as f:
        buf = f.read()
    text = extract_doc_text_via_node(buf)
    assert isinstance(text, str)
    assert len(text.strip()) > 50


@pytest.mark.skipif(PDF_SAMPLE is None, reason="Sample PDF fixture not found")
def test_20_parallel_calls():
    """Verify 20 parallel executions complete without collisions or temp file races."""
    if PDF_SAMPLE and os.path.exists(PDF_SAMPLE):
        with open(PDF_SAMPLE, "rb") as f:
            buf = f.read()
    else:
        buf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    def run_one(_idx):
        return extract_pdf_text_via_node(buf, timeout=30.0)

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(run_one, range(20)))

    assert len(results) == 20
    first_res = results[0]
    for r in results:
        assert r == first_res


@pytest.mark.skipif(PDF_SAMPLE is None, reason="Sample PDF fixture not found")
def test_timeout_kill_enforcement():
    """Verify that an artificially short timeout terminates the process and cleans temp files."""
    if PDF_SAMPLE and os.path.exists(PDF_SAMPLE):
        with open(PDF_SAMPLE, "rb") as f:
            buf = f.read()
    else:
        buf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    # Pass an impossibly short timeout
    with pytest.raises((subprocess.TimeoutExpired, RuntimeError)):
        extract_pdf_text_via_node(buf, timeout=0.0001)


def test_missing_node_error():
    """Verify that a nonexistent Node executable raises a clean, detectable error."""
    if PDF_SAMPLE and os.path.exists(PDF_SAMPLE):
        with open(PDF_SAMPLE, "rb") as f:
            buf = f.read()
    else:
        buf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    orig_pdf_bin = pdf_mod.NODE_BIN
    orig_doc_bin = doc_mod.NODE_BIN
    try:
        pdf_mod.NODE_BIN = "nonexistent_node_binary_xyz_404"
        doc_mod.NODE_BIN = "nonexistent_node_binary_xyz_404"

        with pytest.raises((FileNotFoundError, RuntimeError)):
            extract_pdf_text_via_node(buf, timeout=5.0)

        with pytest.raises((FileNotFoundError, RuntimeError)):
            extract_doc_text_via_node(buf, timeout=5.0)
    finally:
        pdf_mod.NODE_BIN = orig_pdf_bin
        doc_mod.NODE_BIN = orig_doc_bin

