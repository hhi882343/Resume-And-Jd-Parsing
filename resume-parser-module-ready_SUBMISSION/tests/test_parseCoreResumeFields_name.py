import pytest
from src.parseCoreResumeFields import parseCoreFieldsFromResumeText


def test_does_not_return_curriculum_vitae_or_experience_summary_as_the_name():
    cv_only = parseCoreFieldsFromResumeText(
        '\n'.join(['Curriculum Vitae', '', 'Email: test@example.com', '9999999999'])
    )
    assert cv_only['candidateName'] is None

    exp_summary = parseCoreFieldsFromResumeText(
        '\n'.join(['Experience Summary', '', 'Email: narendra@example.com', '8888888888'])
    )
    assert exp_summary['candidateName'] is None


def test_prefers_labeled_name_over_section_headings():
    parsed = parseCoreFieldsFromResumeText(
        '\n'.join([
            'Curriculum Vitae',
            'Name: Mrutyunjaya Mahapatra',
            'Email: mrutyu@example.com',
            '9876543210',
        ])
    )
    assert parsed['candidateName'] == 'Mrutyunjaya Mahapatra'

