import pytest
from src.resumeFieldSanitize import (
    compactHighestQualification,
    looksLikeJobRolePhrase,
    sanitizeDisplayText,
    isCertificationOrNonAcademic,
    normalizeSkillToken,
)
from src.parseCoreResumeFields import parseCoreFieldsFromResumeText
from src.jsRegex import compile_re


def test_compacts_narrative_education_into_clean_degree_specialization():
    hq = compactHighestQualification(
        'Completed Degree in B COM (COMPUTERS) From Acharya Nagarjuna University in April 2021 in'
    )
    assert hq is not None
    assert compile_re(r'B\.?\s*COM', 'i').search(hq)
    assert not compile_re(r'\s+in\s*$', 'i').search(hq)


def test_strips_trailing_periods_from_display_text():
    assert sanitizeDisplayText('Mohammed Junaid.') == 'Mohammed Junaid'


def test_strips_trailing_job_roles_sentences_and_narrative_details_from_degree():
    hq1 = compactHighestQualification(
        'Bachelor of Engineering in Mechanical Engineering. Currently working as a Technical Lead'
    )
    assert hq1 == 'Bachelor of Engineering in Mechanical Engineering'

    hq2 = compactHighestQualification(
        'Strong Engineering professional with a Bachelor of Engineering in Mechanical Engineering. Currently working as a Technical Lead at Tata Technologies, Pune'
    )
    assert hq2 == 'Bachelor of Engineering in Mechanical Engineering'

    hq3 = compactHighestQualification('1. BE Mechanical Amravati University 2017 8.5 CGPA')
    assert hq3 == 'BE Mechanical'

    hq4 = compactHighestQualification('BE Mechanical Amravati University')
    assert hq4 == 'BE Mechanical'

    hq5 = compactHighestQualification(
        'Master of Business Administration (MBA) in Human Resources'
    )
    assert hq5 == 'Master of Business Administration (MBA) in Human Resources'


def test_detects_job_role_phrases_that_belong_in_technology_not_skills():
    assert looksLikeJobRolePhrase('SAP SuccessFactors Consultant') is True
    assert looksLikeJobRolePhrase('SF EC') is False


def test_separates_skills_and_technology_for_sap_profile():
    parsed = parseCoreFieldsFromResumeText(
        '\n'.join([
            'Mohammed Junaid',
            'mohammedjunaidsapsf@gmail.com',
            '+917013044354',
            '',
            'Professional Summary',
            'SAP SuccessFactors Consultant with 3 years experience',
            '',
            'Technical Skills',
            'SF EC, Time Off, Employee Central',
            '',
            'Education',
            'Completed Degree in B COM (COMPUTERS) From Acharya Nagarjuna University in April 2021',
        ])
    )

    assert parsed['candidateName'] == 'Mohammed Junaid'
    assert parsed['highestQualification'] is not None
    assert compile_re(r'COM', 'i').search(parsed['highestQualification'])
    assert not compile_re(r'\s+in\s*$', 'i').search(parsed['highestQualification'])
    assert parsed['skillsRaw'] is not None
    assert compile_re(r'SF EC', 'i').search(parsed['skillsRaw'])
    assert not compile_re(r'SuccessFactors Consultant', 'i').search(parsed['skillsRaw'])
    assert parsed['technologiesRaw'] is not None
    assert compile_re(r'SAP', 'i').search(parsed['technologiesRaw'])
    assert '.' not in parsed['skillsRaw']


