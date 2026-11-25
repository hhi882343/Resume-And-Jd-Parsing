"""Tests for standalone jd_parser module entry points."""

import pytest
from app.core.email_extractor import extract_universal_email_headers
from app.schemas.requirement import AnalyzedRequirement, RequirementData
from jd_parser import parse_email_headers


def test_parse_email_headers_unlabelled_outlook():
    sample = """TPC - Requirement - PLM - Technical Publication - Bangalore
Kallol Chakraborty<Kallol.Chakraborty@Ltts.com>
Arundhati Shivashankarappa Rudagi <Arundhati.Rudagi_ext@Ltts.com>;Pranati Paul <Pranati.Paul_ext@Ltts.com>;K V Sai Siri <Kv.Saisiri_ext@Ltts.com>
Ashwini Kudi C E <Ashwini.Kudi@Ltts.com>
Dear Partner,
"""
    res = parse_email_headers(sample)
    assert res["has_headers"] is True
    assert res["subject"] == "TPC - Requirement - PLM - Technical Publication - Bangalore"
    assert len(res["from"]) == 1
    assert res["from"][0]["email"].lower() == "kallol.chakraborty@ltts.com"
    assert len(res["to"]) == 3
    assert res["to"][0]["email"].lower() == "arundhati.rudagi_ext@ltts.com"
    assert len(res["cc"]) == 1
    assert res["cc"][0]["email"].lower() == "ashwini.kudi@ltts.com"


def test_parse_email_headers_labelled():
    sample = """From: Alice <alice@corp.com>
To: Bob <bob@vendor.com>
Cc: Carol <carol@corp.com>
Subject: Python Dev Opening
"""
    res = parse_email_headers(sample)
    assert res["has_headers"] is True
    assert res["from"][0]["email"] == "alice@corp.com"
    assert res["to"][0]["email"] == "bob@vendor.com"
    assert res["cc"][0]["email"] == "carol@corp.com"


def test_schema_model_instantiation():
    req = AnalyzedRequirement(
        requirementId="req_123",
        roleIndex=1,
        totalRoles=1,
        extractionSource="test",
        jobTitle="Senior Software Engineer",
        overallExperience="5+ years",
        location="Remote",
    )
    dumped = req.model_dump(by_alias=True)
    assert dumped["requirementId"] == "req_123"
    assert dumped["jobTitle"] == "Senior Software Engineer"
    assert dumped["overallExperience"] == "5+ years"
    assert dumped["location"] == "Remote"
