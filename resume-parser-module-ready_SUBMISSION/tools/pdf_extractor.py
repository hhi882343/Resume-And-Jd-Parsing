"""
tools/pdf_extractor.py
Option B Prototype: Python subprocess wrapper around tools/pdf_text.js.
Executes Node.js extractTextWithPdfJs via subprocess without shell, with hard timeout and temporary directory cleanup.
"""
import os
import shutil
import subprocess
import tempfile
from typing import Optional

def get_node_bin() -> str:
    return os.environ.get("NODE_BIN") or shutil.which("node") or "node"

NODE_BIN = get_node_bin()
SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "pdf_text.js"))
DEFAULT_TIMEOUT = 30.0

def extract_pdf_text_via_node(buffer: bytes, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Extract plain text from PDF buffer using the verbatim Node.js extractTextWithPdfJs logic.
    Runs via subprocess with shell=False, timeout, and guaranteed temporary file cleanup.
    """
    node_bin = get_node_bin() if NODE_BIN == "node" else NODE_BIN
    tmp_dir = tempfile.mkdtemp(prefix="pdf_option_b_")
    tmp_pdf = os.path.join(tmp_dir, "input.pdf")
    try:
        with open(tmp_pdf, "wb") as f:
            f.write(buffer)

        proc = subprocess.run(
            [node_bin, SCRIPT_PATH, tmp_pdf],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=timeout,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Node PDF extraction failed (exit code {proc.returncode}): {err}")

        return proc.stdout.decode("utf-8", errors="replace")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

