import pytest
from src.ai.normalize import normalizePhone, normalizeParsedResult

def test_normalize_phone():
    assert normalizePhone("+919876543210") == "+91 98765 43210"
    assert normalizePhone("+11234567890") == "+1 12345 67890"
    assert normalizePhone("9876543210") == "9876543210"
    assert normalizePhone("+919876543210 / +918765432109") == "+91 98765 43210 / +91 87654 32109"

def test_normalize_parsed_result():
    res = normalizeParsedResult({
        "full_name": "John Doe",
        "contact": "+919876543210",
        "email": "john@example.com",
        "total_experience": "5 years",
        "skills": ["Python", "FastAPI"]
    })
    assert res["full_name"] == "John Doe"
    assert res["contact"] == "+91 98765 43210"
    assert res["email"] == "john@example.com"
    assert res["total_experience"] == "5 years"
    assert res["total_experience_years"] == 5.0
    assert res["skills"] == ["Python", "FastAPI"]
