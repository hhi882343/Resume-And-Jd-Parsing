import pytest
from src.ai.experience import (
    cleanExperienceOutput,
    calculateExperienceMonths,
    resolveExperienceFields,
    extractStatedExperienceWording,
)


def test_clean_experience_output():
    assert cleanExperienceOutput("Nearly 12 years of experience") == "12 years"
    assert cleanExperienceOutput("Over 7 years of experience") == "7 years"
    assert cleanExperienceOutput("7+ years of experience") == "7+ years"
    assert cleanExperienceOutput("4.5+ years of experience") == "4.5+ years"
    assert cleanExperienceOutput("36 months") == "36 months"
    assert cleanExperienceOutput("1 year") == "1 year"
    assert cleanExperienceOutput("3 years and 6 months") == "3 years 6 months"


def test_extract_stated_experience_wording():
    resume = "A goal-oriented professional with nearly 12 years of experience in IT."
    assert extractStatedExperienceWording(resume) == "12 years"

    labeled = "Total Experience: 8+ years"
    assert extractStatedExperienceWording(labeled) == "8+ years"


def test_calculate_experience_months():
    periods = [
        {"from": "2020-01", "to": "2021-01"},
        {"from": "2021-01", "to": "2022-01"}
    ]
    assert calculateExperienceMonths(periods) == 25


def test_resolve_experience_fields():
    res = resolveExperienceFields(total_experience="Nearly 12 years of experience")
    assert res["total_experience"] == "12 years"
    assert res["total_experience_months"] == 144
    assert res["total_experience_years"] == 12.0
