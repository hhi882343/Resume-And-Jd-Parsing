import pytest
from src.candidateNameValidation import (
    isBadCandidateDisplayName,
    trimJobTitleSuffixFromDisplayName,
)


def test_rejects_section_titles_mistaken_for_names():
    assert isBadCandidateDisplayName('Curriculum Vitae') is True
    assert isBadCandidateDisplayName('Experience Summary') is True
    assert isBadCandidateDisplayName('CURRICULUM VITAE') is True


def test_rejects_role_heavy_parsed_lines():
    assert isBadCandidateDisplayName('Y. Nagalakshmi Assistant Manager') is True
    assert isBadCandidateDisplayName('Mohammed Junaid Employee Central Time') is True


def test_accepts_plausible_person_names():
    assert isBadCandidateDisplayName('Mrutyunjaya Mahapatra') is False
    assert isBadCandidateDisplayName('Abdul Azizkhan') is False
    assert isBadCandidateDisplayName('Monisha Mohanan') is False


def test_trims_trailing_job_title_tokens():
    assert trimJobTitleSuffixFromDisplayName('Nagalakshmi Assistant Manager') == 'Nagalakshmi'

