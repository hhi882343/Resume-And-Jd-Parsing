"""
Reject résumé section titles / role lines mistaken for person names.
Used by parseCoreResumeFields and resume import fallbacks.
"""
from typing import Optional
import math
from src.jsRegex import compile_re, js_trim, js_split_whitespace

BAD_NAME_EXACT = compile_re(
    r'^(?:career summary|core strengths?|core competencies?|core\s+skills?|key\s+achievements?|'
    r'achievements?|key\s+accomplishments?|software architecture|key responsibilities handled|'
    r'of\s+the\s+company|summary|objective|professional summary|personal summary|executive summary|'
    r'work experience|professional experience|organizations?\s+experience|organizational experience|'
    r'detailed\s+experience|technical competency|skills|key skills|technical skills|profile summary|'
    r'career objective|synopsis|declaration|about\s+me|strengths|candidate assessment sheet|'
    r'st peters engineering college|curriculum\s+vitae|curriculum|vitae|experience\s+summary|'
    r'work\s+summary|employment\s+summary|professional\s+profile|personal\s+profile|resume|'
    r'biodata|resume\s+summary|contact\s+details?|personal\s+details?)$',
    'i'
)

BAD_ROLE_TITLE_LINE = compile_re(
    r'^(?:salesforce|java|\.net|python|react|angular|boomi|mulesoft|full\s*stack|integration|'
    r'network|cloud|cyber|data|machine\s*learning|technical|senior|lead|staff|principal)\s+'
    r'[a-z0-9][a-z0-9\s]+(developer|engineer|consultant|analyst|architect|tester)\b$',
    'i'
)

SECTION_OR_ROLE_WORD = compile_re(
    r'\b(?:curriculum|vitae|experience\s+summary|work\s+summary|professional\s+summary|'
    r'career\s+summary|profile\s+summary|key\s+skills?|technical\s+skills?)\b',
    'i'
)

RE_RESUME_CV_START = compile_re(r'^\b(?:resume|curriculum vitae|cv)\b', 'i')
RE_RESUME_CV_END = compile_re(r'\b(?:resume|curriculum vitae)\s*$', 'i')
RE_TRAILING_PUNCT = compile_re(r'[.,]+$')
RE_WS_SPLIT = compile_re(r'\s+')
RE_HEADING_PREFIX = compile_re(r'^[\s•\-–—]+')
RE_SECTION_HEADING = compile_re(
    r'^(key\s+achievements?|achievements?|key\s+accomplishments?|core\s+competencies?|'
    r'core\s+skills?|core\s+strengths?|professional\s+summary|career\s+summary|'
    r'career\s+objective|technical\s+summary|executive\s+summary|personal\s+summary|'
    r'synopsis|declaration|about\s+me|profile\s+summary|summary|executive\s+profile|'
    r'career\s+profile|professional\s+overview|profile|objective|strengths|'
    r'awards?|certifications?|projects?|work\s+history|employment\s+history|'
    r'organizations?\s+experience|organizational\s+experience|detailed\s+experience|'
    r'technical\s+competency|professional\s+experience|work\s+experience|experience|'
    r'education|skills|technical\s+skills|key\s+skills|of\s+the\s+company|'
    r'curriculum\s+vitae|experience\s+summary|work\s+summary|biodata|resume|contact\s+details?|'
    r'personal\s+details?|personal\s+profile|personal\s+information)$',
    'i'
)

JOB_TITLE_WORDS = {
    'assistant',
    'manager',
    'engineer',
    'developer',
    'consultant',
    'analyst',
    'architect',
    'tester',
    'specialist',
    'lead',
    'senior',
    'junior',
    'employee',
    'central',
    'time',
    'off',
    'instrumentation',
    'instrument',
    'automation',
    'qa',
    'qc',
    'data',
    'azure',
    'cloud',
    'sap',
    'fico',
    'abap',
    'administrator',
    'associate',
    'executive',
    'recruiter',
    'trainer',
    'intern',
    'trainee',
    'officer',
    'supervisor',
    'director',
    'head',
    'vp',
    'professional',
    'technician',
    'programmer',
    'designer',
    'scientist',
}


def is_bad_candidate_display_name(name: Optional[str]) -> bool:
    n = js_trim(str(name or ''))
    if not n or len(n) < 2:
        return True
    if BAD_NAME_EXACT.search(n):
        return True
    if BAD_ROLE_TITLE_LINE.search(n):
        return True
    if SECTION_OR_ROLE_WORD.search(n):
        return True
    if RE_RESUME_CV_START.search(n):
        return True
    if RE_RESUME_CV_END.search(n):
        return True

    words = [w for w in js_split_whitespace(n) if w]
    if len(words) == 0:
        return True

    # Entire line is only job-title vocabulary (e.g. "Employee Central Time").
    lower_words = [RE_TRAILING_PUNCT.sub('', w).lower() for w in words]
    if len(words) >= 2 and all(w in JOB_TITLE_WORDS for w in lower_words):
        return True

    # Trailing job-title run: "Mohammed Junaid Employee Central" / "Nagalakshmi Assistant Manager".
    if len(words) >= 3:
        job_tail = 0
        for i in range(len(lower_words) - 1, -1, -1):
            if lower_words[i] in JOB_TITLE_WORDS:
                job_tail += 1
            else:
                break
        if job_tail >= 2 and job_tail >= math.floor(len(words) / 2):
            return True

    return False


def trim_job_title_suffix_from_display_name(name: Optional[str]) -> Optional[str]:
    tokens = [t for t in js_split_whitespace(name) if t]
    if len(tokens) == 0:
        return None

    lower = [RE_TRAILING_PUNCT.sub('', t).lower() for t in tokens]
    while len(tokens) > 1 and lower[-1] in JOB_TITLE_WORDS:
        tokens.pop()
        lower.pop()

    out = js_trim(' '.join(tokens))
    if not out or is_bad_candidate_display_name(out):
        return None
    return out


def is_resume_section_heading_line(line: str) -> bool:
    s = js_trim(RE_HEADING_PREFIX.sub('', line))
    if not s or len(s) > 90:
        return True
    if is_bad_candidate_display_name(s):
        return True
    return bool(RE_SECTION_HEADING.search(s))


# Alias functions matching JS export names for full backwards/cross compatibility
isBadCandidateDisplayName = is_bad_candidate_display_name
trimJobTitleSuffixFromDisplayName = trim_job_title_suffix_from_display_name
isResumeSectionHeadingLine = is_resume_section_heading_line

