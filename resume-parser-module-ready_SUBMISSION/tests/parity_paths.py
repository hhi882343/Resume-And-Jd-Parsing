import os

TESTS_DIR = os.path.dirname(__file__)

def get_public_parity_dir() -> str:
    cand = os.path.join(TESTS_DIR, "parity_public")
    if os.path.exists(cand):
        return cand
    return os.path.join(TESTS_DIR, "parity")

def get_private_parity_dir() -> str:
    cand = os.path.join(TESTS_DIR, "parity_private")
    if os.path.exists(cand):
        return cand
    return os.path.join(TESTS_DIR, "parity")
