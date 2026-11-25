"""
Keyword / section-based extraction of core resume fields (name, contact, education, skills).
Tuned for common Indian tech resume layouts (header + Education + Technical Skills + Projects).
"""
from typing import Any, Dict, List, Optional, Tuple, Set
import datetime
import math
from src.types import CoreParsedFields
from src.candidateNameValidation import (
    isBadCandidateDisplayName,
    isResumeSectionHeadingLine,
    trimJobTitleSuffixFromDisplayName,
    RE_SECTION_HEADING,
)
from src.resumeFieldSanitize import (
    compactHighestQualification,
    cleanAcademicSpecialization,
    isCertificationOrNonAcademic,
    looksLikeJobRolePhrase,
    normalizeSkillToken,
    sanitizeDisplayText,
    DEGREE_RE,
)
from src.skillsExtractionEngine import (
    detectSkillSection,
    extractDeterministicSkills,
    validateSkillsAgainstSection,
    extractSkillsWithEngineSync,
)
from src.ai.experience import cleanExperienceOutput
from src.jsRegex import compile_re, js_trim, js_split_whitespace, js_split_whitespace_raw
from src.clock import get_current_utc_date

# ============================================================================
# Section Boundary Patterns
# ============================================================================

SECTION_END = (
    r'(?=\n\s*(?:Education|Educational\s+Qualification|Academic\s+Details|Academic\s+Background|'
    r'Highest\s+Qualification|Studies|Technical\s+Skills|Technologies|Skills|Core\s+Skills|'
    r'Key\s+Skills|Skill\s+Set|Domain\s+Proficiency|Technical\s+Expertise|Toolset|Area\s+of\s+Interest|'
    r'Areas\s+of\s+Interest|Areas\s+of\s+Expertise|IT\s+Skills|Computer\s+Skills|Experience|'
    r'Professional\s+Experience|Relevant\s+Experience|Work\s+Experience|Employment|Current\s+Company|'
    r'Projects?|PROJECT(?:-\d+)?|Certifications?|Certification|Career\s+Highlights:?|Highlights:?|'
    r'Additional\s+Information|Interests|Summary|Objective|Synopsis|Declaration|'
    r'(?:Key|Professional|Career|Major|Notable)\s+Achievements?|Achievements?|Contact|Personal|References|Location)\b)'
)

SKILL_SECTION_START = (
    r'(?:Technical\s+Skills|Core\s+Skills|Key\s+Skills|Technologies|Technology\s+Stack|'
    r'Programming\s+Languages|Programming\s+Skills|Skills\s*(?:&|and)\s*Technologies|'
    r'Professional\s+Skills|Profession(?:al)?\s+Skills|Relevant\s+Skills|Software\s+Skills|'
    r'IT\s+Skills|Computer\s+Skills|Functional\s+Skills|Domain\s+Proficiency|Technical\s+Expertise|'
    r'Technical\s+Competencies|Toolset|Area\s+of\s+Interest|Areas\s+of\s+Interest|Areas\s+of\s+Expertise|'
    r'Tech\s+Stack|Tools\s+and\s+Technologies|Tools\s*&\s*Technologies|Professional\s+Expertise|'
    r'Summary\s+of\s+Skills|Skills\s+Profile|Skills?\s+Set|Skill\s+Set)'
)

EDUCATION_SECTION_START = (
    r'(?:Education(?:\s+details|\s+qualifications?|\s+background|\s+history|\s+summary|\s+profile)?|'
    r'Educational\s+Qualifications?|Educational\s+Details|Academic\s+Qualifications?|'
    r'Academic\s+Background|Academic\s+Details|Academic\s+Record|Highest\s+Qualification|'
    r'Studies|Qualifications?|Educational\s+Background|Degrees?(?:\s+details)?)'
)


def split_lines(text: str) -> List[str]:
    return [
        js_trim(l.replace('\u00a0', ' ').replace('**', ''))
        for l in text.splitlines()
    ]


RE_WORK_EXP_SEARCH = compile_re(
    r'\n\s*(?:Professional\s+Experience|Work\s+Experience|Employment\s+History|Organizational\s+Experience|Detailed\s+Experience|Career\s+History)\b',
    'i'
)


def slice_resume_header_for_contacts(text: str) -> str:
    m = RE_WORK_EXP_SEARCH.search(text)
    if m:
        cut = m.start()
        if 350 < cut < 80000:
            return text[:cut]
    return text[:min(len(text), 9000)]


def extract_between_sections(full_text: str, start_names: Any, end_before: Any) -> Optional[str]:
    re_pat = compile_re(f"(?:{start_names.pattern})\\s*\\n([\\s\\S]*?)(?:{end_before.pattern}|$)", 'i')
    m = re_pat.search(full_text)
    if m and m.group(1) and js_trim(m.group(1)):
        return js_trim(m.group(1))
    return None


RE_EDU_BLOCK_1 = compile_re(
    f"(?:^|\\n)\\s*(?:{EDUCATION_SECTION_START})\\s*:?\\s*\\n([\\s\\S]*?)(?:{SECTION_END}|$)",
    'i'
)
RE_EDU_BLOCK_2 = compile_re(
    f"(?:^|\\n)\\s*(?:{EDUCATION_SECTION_START})\\s*:?\\s*\\n([\\s\\S]*?)(?=\\n\\s*(?:{SKILL_SECTION_START}|Technical\\s+Skills|Experience|Projects|Certifications?)\\b|$)",
    'i'
)
RE_EDU_START = compile_re(f"(?:^|\\n)\\s*(?:{EDUCATION_SECTION_START})\\s*:?\\s*\\n", 'i')
RE_EDU_STOP = compile_re(
    f"\\n\\s*(?:{SKILL_SECTION_START}|Technical\\s+Skills|Core\\s+Skills|Skills|Experience|Projects|Certifications?)\\b",
    'i'
)


def slice_education_block(text: str) -> Optional[str]:
    m = RE_EDU_BLOCK_1.search(text)
    if m and m.group(1) and js_trim(m.group(1)):
        return js_trim(m.group(1))
    m = RE_EDU_BLOCK_2.search(text)
    if m and m.group(1) and js_trim(m.group(1)):
        return js_trim(m.group(1))
    return extract_between_sections(text, RE_EDU_START, RE_EDU_STOP)


ELIGIBLE_SKILLS_HEADING_RE = compile_re(
    r'^(?:technical\s+skills?|core\s+skills?|key\s+skills?|relevant\s+skills?|software\s+skills?|'
    r'skills?|tools\s*(?:&|and|/)\s*technologies|technologies\s*(?:&|and|/)\s*tools|technical\s+competencies|'
    r'core\s+competencies|core\s+technical\s+capabilities|technical\s+proficiencies|technical\s+proficiency|'
    r'technical\s+expertise|professional\s+expertise|professional\s+skills?|areas?\s+of\s+expertise|'
    r'software|tools|technologies|technology\s+stack|tech\s+stack|programming\s+languages?|'
    r'programming\s+skills?|it\s+skills?|computer\s+skills?|skills?\s*set|skills?\s+profile|'
    r'skills?\s+summary|skillset)$',
    'i'
)

PROHIBITED_HEADING_RE = compile_re(
    r'\b(?:responsibilit|experience|employment|work\s+history|career\s+history|project|education|'
    r'academic|qualification|summary|objective|profile|certificat|training|internship|achievement|'
    r'award|declaration|personal|contact|reference|synopsis)\b',
    'i'
)


def extract_eligible_skills_block(text: str) -> Optional[str]:
    detected = detectSkillSection(text)
    if detected and detected.get('content') and js_trim(detected['content']):
        return js_trim(detected['content'])
    return None


def slice_technical_skills_block(text: str) -> Optional[str]:
    return extract_eligible_skills_block(text)


RE_EMAIL_LABELED_1 = compile_re(
    r'(?:email|e-?mail|contact\s+email)\s*[:\-]\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})',
    'gi'
)
RE_EMAIL_LABELED_2 = compile_re(
    r'(?:email|e-?mail|mail)\s*[:\-]?\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})',
    'gi'
)
RE_EMAIL_ANY = compile_re(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', 'gi')
RE_EMAIL_VALID = compile_re(r'^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$', 'i')
RE_EMAIL_DISCARD = compile_re(r'(?:example|test|sample|dummy|resume|candidate)\.(?:com|org|net)$', 'i')


def extract_email_from_chunk(chunk: str) -> Optional[str]:
    for re_pat in [RE_EMAIL_LABELED_1, RE_EMAIL_LABELED_2]:
        for m in re_pat.finditer(chunk):
            grp = m.group(1) or ''
            clean = js_trim(compile_re(r'^mailto:', 'i').sub('', grp))
            if not RE_EMAIL_VALID.search(clean):
                continue
            if RE_EMAIL_DISCARD.search(clean):
                continue
            return clean.lower()

    for m in RE_EMAIL_ANY.finditer(chunk):
        raw = m.group(0)
        clean = js_trim(compile_re(r'^mailto:', 'i').sub('', raw))
        if not RE_EMAIL_VALID.search(clean):
            continue
        if RE_EMAIL_DISCARD.search(clean):
            continue
        return clean.lower()

    return None


def extract_email(text: str) -> Optional[str]:
    head = slice_resume_header_for_contacts(text)
    return extract_email_from_chunk(head) or extract_email_from_chunk(text)


PHONE_PATTERNS = [
    compile_re(r'(?:\+91[-\s.]?)?[6-9]\d{9}\b', 'g'),
    compile_re(r'\(\+91\)\s*[6-9]\d{9}\b', 'g'),
    compile_re(r'\(\s*\+91\s*\)\s*[6-9]\d{9}\b', 'g'),
    compile_re(r'\b\+1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', 'g'),
    compile_re(r'\b\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b', 'g'),
    compile_re(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b', 'g'),
    compile_re(r'\+\d{1,3}[-\s]?\d[\d\s().-]{8,14}\d', 'g'),
    compile_re(r'(?:phone|phone\s*no\.?|mobile|mob|tel|cell|contact|contact\s*number|ph\.?\s*no\.?)\s*[:\-]?\s*([+\d\s().-]{10,})', 'gi'),
]

RE_PHONE_PREFIX_CLEAN = compile_re(
    r'^(?:phone|phone\s*no\.?|mobile|mob|tel|cell|contact|contact\s*number|ph\.?\s*no\.?)\s*[:\-]?\s*',
    'i'
)
RE_NON_PHONE_CHARS = compile_re(r'[^\d+]')


def extract_phone_from_chunk(chunk: str) -> Optional[str]:
    for pattern in PHONE_PATTERNS:
        for m in pattern.finditer(chunk):
            phone = m.group(0)
            clean = js_trim(RE_PHONE_PREFIX_CLEAN.sub('', phone))
            clean = RE_NON_PHONE_CHARS.sub('', clean)
            if 10 <= len(clean) <= 15:
                if len(clean) == 10 and clean[0] in '6789':
                    return f"+91 {clean[:5]} {clean[5:]}"
                if clean.startswith('91') and len(clean) == 12:
                    return f"+{clean[:2]} {clean[2:7]} {clean[7:]}"
                if clean.startswith('+'):
                    return clean
                if len(clean) == 10:
                    return clean
    return None


def extract_phone(text: str) -> Optional[str]:
    head = slice_resume_header_for_contacts(text)
    return extract_phone_from_chunk(head) or extract_phone_from_chunk(text)


RE_LINKEDIN_COLLAPSE_1 = compile_re(r'(https?):\/\/+\s*', 'gi')
RE_LINKEDIN_COLLAPSE_2 = compile_re(r'[\u00a0\t]', 'g')
RE_LINKEDIN_COLLAPSE_3 = compile_re(r'\s+', 'g')
RE_LINKEDIN_CLEAN_PUNCT = compile_re(r'[.,;:)]+$')
RE_LINKEDIN_MATCH_CHECK = compile_re(r'linkedin\.com/(?:in|pub)/', 'i')
RE_LINKEDIN_HTTP_CHECK = compile_re(r'^https?://', 'i')
RE_LINKEDIN_WWW_CHECK = compile_re(r'^www\.', 'i')
RE_LINKEDIN_NO_WWW = compile_re(r'^https://linkedin\.com', 'i')

UID_PART = r'[a-zA-Z0-9_%\-]{1,200}'
SLUG_PART = r'[a-zA-Z0-9](?:[a-zA-Z0-9_-]{1,98}[a-zA-Z0-9])'

LINKEDIN_PATTERNS = [
    compile_re(f"https?://(?:[a-z]{{2}}\\.)?(?:www\\.)?linkedin\\.com/(?:in|pub)/{UID_PART}", 'gi'),
    compile_re(f"(?:^|\\s)www\\.linkedin\\.com/(?:in|pub)/{UID_PART}", 'gi'),
    compile_re(f"(?:^|\\s)linkedin\\.com/(?:in|pub)/{UID_PART}", 'gi'),
    compile_re(f"linkedin\\s*\\.\\s*com\\s*/\\s*(?:in|pub)\\s*/\\s*{UID_PART}", 'gi'),
]

RE_LINKEDIN_LABELED = compile_re(
    f"(?:^|\\s)(?:linkedin|linked\\s*in)\\s*[:\\-]\\s*(https?://[^\\s]+|(?:www\\.)?linkedin\\.com/(?:in|pub)/{UID_PART})",
    'i'
)
RE_SHORT_LABELED = compile_re(
    f"(?:^|\\s)(?:linkedin|linked\\s*in|profile)\\s*[:\\s-]*\\s*in\\s*/\\s*({SLUG_PART})",
    'gi'
)
RE_BARE_IN_PATH = compile_re(
    f"(?:^|\\s)in\\s*/\\s*({SLUG_PART})(?=[\\s.,;)|]|$)",
    'gi'
)
RE_VALID_SLUG = compile_re(r'^[a-zA-Z0-9](?:[a-zA-Z0-9_-]*[a-zA-Z0-9])?$')


def normalize_linkedin_profile_url(raw: str) -> Optional[str]:
    s = js_trim(raw).replace(' ', '')
    s = s.split('?')[0].split('#')[0]
    s = compile_re(r'/+$').sub('', s)
    s = RE_LINKEDIN_CLEAN_PUNCT.sub('', s)
    if not RE_LINKEDIN_MATCH_CHECK.search(s):
        return None
    if not RE_LINKEDIN_HTTP_CHECK.search(s):
        s = compile_re(r'^//').sub('', s)
        s = 'https://www.' + RE_LINKEDIN_WWW_CHECK.sub('', s)
    elif RE_LINKEDIN_NO_WWW.search(s):
        s = RE_LINKEDIN_NO_WWW.sub('https://www.linkedin.com', s)
    return s


def extract_linkedin(text: str) -> Optional[str]:
    collapsed = RE_LINKEDIN_COLLAPSE_1.sub(r'\1://', text)
    collapsed = RE_LINKEDIN_COLLAPSE_2.sub(' ', collapsed)
    collapsed = RE_LINKEDIN_COLLAPSE_3.sub(' ', collapsed)

    class Hit:
        def __init__(self, url: str, idx: int):
            self.url = url
            self.idx = idx

    hits: List[Hit] = []

    def try_push(fragment: str, idx: int):
        n = normalize_linkedin_profile_url(fragment)
        if n:
            hits.append(Hit(url=n, idx=idx))

    for re_pat in LINKEDIN_PATTERNS:
        for m in re_pat.finditer(collapsed):
            raw_match = m.group(0) or ''
            frag = js_trim(raw_match)
            if compile_re(r'^linkedin\s*\.', 'i').search(frag):
                frag = frag.replace(' ', '')
            elif raw_match.startswith(' '):
                frag = raw_match.lstrip()
            if not RE_LINKEDIN_HTTP_CHECK.search(frag):
                if frag.startswith('www.linkedin.com'):
                    frag = f"https://{frag}"
                elif frag.startswith('linkedin.com'):
                    frag = f"https://www.{frag}"
            try_push(frag, m.start())

    labeled = RE_LINKEDIN_LABELED.search(collapsed)
    if labeled and labeled.group(1):
        frag = js_trim(labeled.group(1))
        if not RE_LINKEDIN_HTTP_CHECK.search(frag):
            frag = RE_LINKEDIN_WWW_CHECK.sub('', frag)
            frag = f"https://www.{frag}"
        try_push(frag, labeled.start())

    def looks_like_li_slug(s: str) -> bool:
        t = RE_LINKEDIN_CLEAN_PUNCT.sub('', s)
        if len(t) < 3 or len(t) > 100:
            return False
        if compile_re(r'^\d+$').search(t):
            return False
        return bool(RE_VALID_SLUG.search(t))

    def push_slug(slug: str, idx: int):
        t = RE_LINKEDIN_CLEAN_PUNCT.sub('', js_trim(slug))
        if not looks_like_li_slug(t):
            return
        hits.append(Hit(url=f"https://www.linkedin.com/in/{t}", idx=idx))

    for sm in RE_SHORT_LABELED.finditer(collapsed):
        g = sm.group(1)
        if g:
            push_slug(g, sm.start())

    for sm in RE_BARE_IN_PATH.finditer(collapsed):
        g = sm.group(1)
        if g:
            push_slug(g, sm.start())

    if not hits:
        return None
    hits.sort(key=lambda h: h.idx)
    seen: Set[str] = set()
    for h in hits:
        k = h.url.lower()
        if k not in seen:
            seen.add(k)
            return h.url
    return hits[0].url if hits else None


def finalize_candidate_name(candidate: Optional[str]) -> Optional[str]:
    if not candidate:
        return None
    trimmed = sanitizeDisplayText(trimJobTitleSuffixFromDisplayName(candidate) or js_trim(candidate))
    if isBadCandidateDisplayName(trimmed):
        return None
    return trimmed


RE_NAME_CLEAN_PREFIX = compile_re(r'^[\s:–—\-]+')
RE_NAME_CLEAN_DELIM = compile_re(r'\s*[,;]\s*.*$')
RE_NAME_DISQUALIFY = compile_re(
    r'\b(?:key skills|technical skills|professional summary|career objective|core strengths?|key\s+achievements?)\b',
    'i'
)
RE_ALL_CAPS_NAME = compile_re(r'^[A-Z][A-Z\s.\'-]{2,80}$')
RE_TITLE_CASE_NAME = compile_re(r'^[A-Za-z][A-Za-z.\'-]*(?:\s+(?:[A-Za-z][A-Za-z.\'-]*|[A-Za-z]\.)){0,6}$')


def clean_extracted_name(raw: str) -> Optional[str]:
    s = js_trim(RE_NAME_CLEAN_PREFIX.sub('', raw))
    s = js_trim(s.split('|')[0])
    s = RE_NAME_CLEAN_DELIM.sub('', s)
    s = js_trim(compile_re(r'\s+', 'g').sub(' ', s))
    if not s or len(s) > 90:
        return None
    if isBadCandidateDisplayName(s):
        return None
    if RE_NAME_DISQUALIFY.search(s):
        return None

    if RE_ALL_CAPS_NAME.search(s):
        cap = compile_re(r'\b\w').sub(lambda m: m.group(0).upper(), s.lower())
        return finalize_candidate_name(cap)

    if RE_TITLE_CASE_NAME.search(s):
        return finalize_candidate_name(s)

    return None


NAME_LABELED_PATTERNS = [
    compile_re(r'(?:^|\n)\s*(?:Name|Candidate\s*Name|Full\s*Name)\s*[:]\s*([^\n]+)', 'i'),
    compile_re(r'(?:^|\n)\s*(?:Name|Candidate\s*Name|Full\s*Name)\s*[-–—]\s*([^\n]+)', 'i'),
    compile_re(r'(?:^|\n)\s*(?:Name|Candidate\s*Name|Full\s*Name)\s*\*?\s*(?:[:\-–—]\s*)?([A-Z][^\n]{1,80})', 'i'),
]


def extract_name_from_labeled_fields(full_text: str) -> Optional[str]:
    for re_pat in NAME_LABELED_PATTERNS:
        m = re_pat.search(full_text)
        if m and m.group(1):
            cleaned = clean_extracted_name(m.group(1).split('\t')[0])
            if cleaned:
                return cleaned
    return None


RE_HEADER_STOP = compile_re(
    r'^(objective|summary|career\s+summary|experience\s+summary|work\s+summary|curriculum\s+vitae|'
    r'curriculum|vitae|education|work\s+experience|professional\s+experience|organizations?\s+experience|'
    r'experience|skills|technical|projects|contact|personal|profile|core\s+strengths?|career\s+objective|'
    r'key\s+achievements?|achievements?|synopsis|declaration|about\s+me|strengths|technical\s+competency|biodata|resume)$',
    'i'
)
RE_SKIP_LINE = compile_re(r'[@/:]|linkedin|github\.com|\.com/in/|^\d[\d\s().+-]{8,}$|^[+()]', 'i')
RE_LOCATION_ONLY = compile_re(r'^(hyderabad|bengaluru|bangalore|chennai|mumbai|delhi|pune|kolkata|india)\b', 'i')
RE_LINE_NAME_LABELED = compile_re(r'^(?:name|candidate|full\s*name)\s*[:\-]\s*(.+)$', 'i')
RE_CLEAN_PREFIX_BULLET = compile_re(r'^[\s•\-–—]+')
RE_STANDARD_NAME = compile_re(r'^[A-Z][a-z]+(?:\s+(?:[A-Z][a-z]+|[A-Z]\.)){1,4}$')
RE_ALL_CAPS_SHORT = compile_re(r'^[A-Z][A-Z.\s]{2,50}$')
RE_HAS_TWO_CAPS = compile_re(r'[A-Z]{2,}')


def extract_name(lines: List[str], full_text: str) -> Optional[str]:
    from_labels = extract_name_from_labeled_fields(full_text)
    if from_labels:
        return from_labels

    for i in range(min(28, len(lines))):
        raw_line = lines[i]
        line = js_trim(RE_CLEAN_PREFIX_BULLET.sub('', raw_line))
        if not line or len(line) > 90:
            continue
        if RE_SKIP_LINE.search(line) or RE_HEADER_STOP.search(line):
            continue
        if RE_LOCATION_ONLY.search(line) and compile_re(r',\s*india', 'i').search(line):
            continue

        labeled = RE_LINE_NAME_LABELED.search(line)
        if labeled and labeled.group(1):
            n = clean_extracted_name(labeled.group(1))
            if n:
                return n

        if RE_STANDARD_NAME.search(line) and 4 <= len(line) <= 60:
            name = finalize_candidate_name(line)
            if name:
                return name

        if (
            RE_ALL_CAPS_SHORT.search(line)
            and RE_HAS_TWO_CAPS.search(line)
            and 2 <= len(js_split_whitespace_raw(line)) <= 5
            and len(line) <= 60
        ):
            if not isResumeSectionHeadingLine(line):
                cap = compile_re(r'\b\w').sub(lambda m: m.group(0).upper(), line.lower())
                name = finalize_candidate_name(cap)
                if name:
                    return name

    email_line_idx = -1
    for idx, l in enumerate(lines):
        if compile_re(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', 'i').search(l):
            email_line_idx = idx
            break

    if email_line_idx > 0:
        prev = js_trim(RE_CLEAN_PREFIX_BULLET.sub('', lines[email_line_idx - 1]))
        if prev and 2 <= len(prev) <= 80 and not RE_SKIP_LINE.search(prev) and not RE_HEADER_STOP.search(prev):
            if compile_re(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}$').search(prev) and not isResumeSectionHeadingLine(prev):
                name = finalize_candidate_name(prev)
                if name:
                    return name
            if (
                compile_re(r'^[A-Z][A-Z\s]{2,50}$').search(prev)
                and 2 <= len(js_split_whitespace_raw(prev)) <= 5
                and not isResumeSectionHeadingLine(prev)
            ):
                cap = compile_re(r'\b\w').sub(lambda m: m.group(0).upper(), prev.lower())
                name = finalize_candidate_name(cap)
                if name:
                    return name

    m = compile_re(r'(?:^|\n)\s*(?:name|full\s*name)\s*[:\-]\s*([^\n]+)', 'i').search(full_text)
    if m and m.group(1):
        c = clean_extracted_name(m.group(1))
        if c:
            return c

    return None


DEGREE_TIERS = [
    {'re': compile_re(r'\b(ph\.?\s*d|phd|doctorate|doctoral|doctor\s+of\s+philosophy)\b', 'i'), 'rank': 100},
    {'re': compile_re(r'\b(m\.?\s*phil|m\.?\s*philosophy)\b', 'i'), 'rank': 88},
    {
        're': compile_re(
            r'\b(m\.?\s*tech|m\.?\s*e\.?|m\.?\s*sc|m\.?\s*com|mca|mba|pgdm|pgdca|post\s*graduate(?:\s+diploma)?|post-?grad|msc|m\.?\s*sc\.|ms\s+in|master(?:\'s)?\s+(?:degree|of\b|in\b)|master\s+degree)\b',
            'i'
        ),
        'rank': 75,
    },
    {
        're': compile_re(
            r'\b(b\.?\s*tech|b\.?\s*e\.?|b\.?\s*e\b|bachelor|b\.?\s*sc|b\.?\s*com\.?|b\.?\s*com\b|bca|bba|b\.?\s*ba|b\.?\s*arch|b\.?\s*pharm|under\s*graduate|undergraduate|u\.?g\.?)\b',
            'i'
        ),
        'rank': 55,
    },
    {'re': compile_re(r'\b(diploma(?:\s+in\b)?|polytechnic|d\.?\s*tech\s*\(diploma\)|associate(?:\s+degree)?)\b', 'i'), 'rank': 42},
    {
        're': compile_re(
            r'\b(12\s*th|twelfth|hsc|h\.?\s*s\.?\s*c|intermediate|\+2|plus\s*two|puc|senior\s*secondary|class\s*xii|class\s*12)\b',
            'i'
        ),
        'rank': 32,
    },
    {
        're': compile_re(
            r'\b(10\s*th|tenth|ssc|s\.?\s*s\.?\s*c|matric|matriculation|sslc|class\s*10|class\s*x\b)\b',
            'i'
        ),
        'rank': 22,
    },
]


def rank_line_for_degree(line: str) -> int:
    if isCertificationOrNonAcademic(line):
        return 0
    max_rank = 0
    for tier in DEGREE_TIERS:
        if tier['re'].search(line):
            max_rank = max(max_rank, tier['rank'])
    return max_rank


def strip_marks_from_education_text(s: str) -> str:
    t = js_trim(compile_re(r'\s+', 'g').sub(' ', s))
    if not t:
        return ''
    t = compile_re(r'\b(?:cgpa|sgpa|gpa)\s*[:\-]?\s*[\d.]+\s*(?:/\s*\d+)?\b', 'gi').sub(' ', t)
    t = compile_re(r'\b(?:percentage|aggregate|marks?|scores?)\s*[:\-]?\s*[\d.]+\s*%?\b', 'gi').sub(' ', t)
    t = compile_re(r'\b\d+(?:\.\d+)?\s*%\b', 'g').sub(' ', t)
    t = compile_re(r'\b(?:distinction|first\s*class|second\s*class|with\s+honou?rs)\b', 'gi').sub(' ', t)
    t = compile_re(r'\s*[,;]?\s*(?:19|20)\d{2}\s*[-–]\s*(?:19|20)\d{2}\b', 'g').sub(' ', t)
    return js_trim(compile_re(r'\s+', 'g').sub(' ', t))


def pick_best_education_from_block(education_block: Optional[str]) -> Dict[str, Any]:
    if not education_block or not js_trim(education_block):
        return {'highestQualification': None, 'educationItems': []}

    raw_lines = [
        js_trim(RE_CLEAN_PREFIX_BULLET.sub('', l))
        for l in education_block.splitlines()
        if js_trim(RE_CLEAN_PREFIX_BULLET.sub('', l))
        and not compile_re(r'^(project(?:-\d+)?|description|roles?|team\s*size)\b', 'i').search(js_trim(RE_CLEAN_PREFIX_BULLET.sub('', l)))
        and not isCertificationOrNonAcademic(js_trim(RE_CLEAN_PREFIX_BULLET.sub('', l)))
    ]

    if not raw_lines:
        return {'highestQualification': None, 'educationItems': []}

    stripped = [strip_marks_from_education_text(l) for l in raw_lines]
    max_r = max((rank_line_for_degree(l) for l in stripped), default=0)
    if max_r <= 0:
        return {'highestQualification': None, 'educationItems': []}

    tier_rows = [
        {'line': line, 'idx': idx, 'r': rank_line_for_degree(line)}
        for idx, line in enumerate(stripped)
        if rank_line_for_degree(line) == max_r
    ]

    pick = tier_rows[0]
    for row in tier_rows:
        if pick and len(row['line']) > len(pick['line']):
            pick = row

    if not pick:
        return {'highestQualification': None, 'educationItems': []}

    cleaned = cleanAcademicSpecialization(pick['line'])
    return (
        {'highestQualification': cleaned, 'educationItems': [cleaned]}
        if cleaned
        else {'highestQualification': None, 'educationItems': []}
    )


def slice_resume_head_for_education_fallback(full_text: str) -> str:
    markers = [
        compile_re(
            r'\n\s*(?:Professional\s+Experience|Work\s+Experience|Employment\s+History|Career\s+Snapshot|Organizational\s+Experience|Detailed\s+Experience|Experience\s*[\|:])',
            'i'
        ),
        compile_re(r'\n\s*(?:PROJECT|Project)[\s_-]?\d', 'i'),
    ]
    cut = len(full_text)
    for rx in markers:
        m = rx.search(full_text)
        if m and 200 <= m.start() < cut:
            cut = m.start()
    if cut != len(full_text):
        return full_text[:cut]
    return full_text[:min(len(full_text), 4800)]


def extract_highest_qualification_from_any_text(text: str) -> Optional[str]:
    lines = [
        js_trim(compile_re(r'\s+', 'g').sub(' ', RE_CLEAN_PREFIX_BULLET.sub('', l)))
        for l in text.splitlines()
        if js_trim(compile_re(r'\s+', 'g').sub(' ', RE_CLEAN_PREFIX_BULLET.sub('', l)))
        and len(js_trim(compile_re(r'\s+', 'g').sub(' ', RE_CLEAN_PREFIX_BULLET.sub('', l)))) < 180
        and not isCertificationOrNonAcademic(js_trim(compile_re(r'\s+', 'g').sub(' ', RE_CLEAN_PREFIX_BULLET.sub('', l))))
    ]

    best: Optional[Dict[str, Any]] = None
    for line in lines:
        r = rank_line_for_degree(line)
        if r <= 0:
            continue
        if compile_re(r'\b(responsible|managed|leading\s+a|team\s+of|delivered|implemented|designed|client:|stakeholder)\b', 'i').search(line):
            continue
        if (
            len(line) > 95
            and not compile_re(r'\b(university|college|institute|polytechnic|school|board|cgpa|gpa|graduation|aggregate|%\b|\d{4})\b', 'i').search(line)
            and not DEGREE_RE.search(line)
        ):
            continue
        cleaned = cleanAcademicSpecialization(line)
        if not cleaned:
            continue
        if not best or r > best['rank'] or (r == best['rank'] and len(cleaned) > len(best['value'])):
            best = {'rank': r, 'value': cleaned}

    if not best or not best.get('value'):
        return None
    return cleanAcademicSpecialization(best['value'])


def looks_like_education_row(line: str) -> bool:
    if isCertificationOrNonAcademic(line):
        return False
    if rank_line_for_degree(line) > 0:
        return True
    if compile_re(r'\b(university|college|institute|polytechnic|school|board|cgpa|gpa|\d{1,2}\.\d\s*cgpa|%\s*\d|graduation|year\s+of\s+passing)\b', 'i').search(line):
        return True
    if compile_re(r'\b(?:19|20)\d{2}\b').search(line) and len(line) < 130:
        return True
    return False


def extract_education_items(education_block: Optional[str]) -> List[str]:
    if not education_block:
        return []

    tokens = compile_re(r'\n|[;•]').split(education_block)
    items: List[str] = []
    seen: Set[str] = set()

    for token in tokens:
        line = js_trim(compile_re(r'\s+', 'g').sub(' ', RE_CLEAN_PREFIX_BULLET.sub('', token)))
        if 2 < len(line) < 180 and not isCertificationOrNonAcademic(line):
            if not compile_re(r'^(project(?:-\d+)?|description|roles?|team\s*size|duration|customer|tools?)\b', 'i').search(line):
                if looks_like_education_row(line):
                    cleaned = cleanAcademicSpecialization(strip_marks_from_education_text(line)) or ''
                    if 2 < len(cleaned) < 180 and cleaned not in seen:
                        seen.add(cleaned)
                        items.append(cleaned)

    return items[:2]


MONTH_MAP = {
    'jan': 0, 'january': 0, 'feb': 1, 'february': 1, 'mar': 2, 'march': 2,
    'apr': 3, 'april': 3, 'may': 4, 'jun': 5, 'june': 5, 'jul': 6, 'july': 6,
    'aug': 7, 'august': 7, 'sep': 8, 'sept': 8, 'september': 8,
    'oct': 9, 'october': 9, 'nov': 10, 'november': 10, 'dec': 11, 'december': 11,
}


def parse_experience_date_token(val: str) -> Optional[Dict[str, Any]]:
    s = js_trim(val).lower()
    if not s:
        return None
    if compile_re(r'^(present|current|now|till\s+date|till\s+now|ongoing)$', 'i').search(s):
        now = get_current_utc_date()
        return {'year': now.year, 'month': now.month - 1, 'isPresent': True}

    named = compile_re(r'^([a-z]+)\s*[\',]?\s*(\d{4})$', 'i').search(s)
    if named and named.group(1) and named.group(2) and named.group(1).lower() in MONTH_MAP:
        return {'year': int(named.group(2)), 'month': MONTH_MAP[named.group(1).lower()]}

    named_short = compile_re(r'^([a-z]+)\s*[\']?\s*(\d{2})$', 'i').search(s)
    if named_short and named_short.group(1) and named_short.group(2) and named_short.group(1).lower() in MONTH_MAP:
        yr = 2000 + int(named_short.group(2))
        return {'year': yr, 'month': MONTH_MAP[named_short.group(1).lower()]}

    mm_yyyy = compile_re(r'^(\d{1,2})[-/](\d{4})$').search(s)
    if mm_yyyy and mm_yyyy.group(1) and mm_yyyy.group(2):
        m = int(mm_yyyy.group(1))
        if 1 <= m <= 12:
            return {'year': int(mm_yyyy.group(2)), 'month': m - 1}

    yyyy_mm = compile_re(r'^(\d{4})[-/](\d{1,2})$').search(s)
    if yyyy_mm and yyyy_mm.group(1) and yyyy_mm.group(2):
        m = int(yyyy_mm.group(2))
        if 1 <= m <= 12:
            return {'year': int(yyyy_mm.group(1)), 'month': m - 1}

    year_only = compile_re(r'^(\d{4})$').search(s)
    if year_only and year_only.group(1):
        yr = int(year_only.group(1))
        if 1970 <= yr <= 2050:
            return {'year': yr}

    return None


RE_EXP_MATCH_1 = compile_re(
    r'(?:^|\n)\s*(?:Professional\s+Experience|Work\s+Experience|Employment\s+History|Experience|Career\s+History|Work\s+History|Employment)\s*:?\s*(?:\n|$)([\s\S]*?)(?=(?:^|\n)\s*(?:Education|Educational\s+Qualifications?|Academic\s+Details|Academic\s+Background|Technical\s+Skills|Skills|Core\s+Skills|Key\s+Skills|Projects?|Academic\s+Projects?|Certifications?|Declaration)\b|$)',
    'i'
)
RE_EXP_MATCH_2 = compile_re(
    r'(?:Professional\s+Experience|Work\s+Experience|Employment\s+History|Experience)\b[:\s]*([\s\S]*?)(?=(?:Education|Technical\s+Skills|Skills|Projects?|Declaration)\b|$)',
    'i'
)
RE_DATE_RANGE = compile_re(
    r'\b((?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,\']*\d{2,4}|\d{1,2}[-/]\d{2,4}|\d{4}))\s*(?:[-–—]|\bto\b)\s*((?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,\']*\d{2,4}|\d{1,2}[-/]\d{2,4}|\d{4}|present|current|till\s+date|till\s+now|now|ongoing))\b',
    'gi'
)


def calculate_experience_from_work_history(full_text: str) -> Optional[str]:
    m1 = RE_EXP_MATCH_1.search(full_text)
    m2 = RE_EXP_MATCH_2.search(full_text)
    exp_match = m1 or m2
    search_section = exp_match.group(1) if exp_match and exp_match.group(1) else full_text

    if not exp_match or not exp_match.group(1):
        edu_block = slice_education_block(full_text)
        if edu_block:
            search_section = search_section.replace(edu_block, '')

    intervals: List[Tuple[int, int]] = []

    def process_match(start_token: str, end_token: str):
        start = parse_experience_date_token(start_token)
        end = parse_experience_date_token(end_token)
        if not start or not end:
            return

        is_year_only = start.get('month') is None and end.get('month') is None and not end.get('isPresent')
        if is_year_only:
            if end['year'] < start['year']:
                return
            start_idx = start['year'] * 12
            end_idx = end['year'] * 12
        else:
            start_idx = start['year'] * 12 + start.get('month', 0)
            if end.get('isPresent'):
                end_idx = end['year'] * 12 + end['month']
            elif end.get('month') is not None:
                end_idx = end['year'] * 12 + end['month'] + 1
            else:
                end_idx = end['year'] * 12 + 12
            if end_idx < start_idx:
                return

        intervals.append((start_idx, end_idx))

    for line in search_section.splitlines():
        if compile_re(r'\b(?:intern|internship|academic\s+project|coursework|training)\b', 'i').search(line):
            continue
        for m in RE_DATE_RANGE.finditer(line):
            process_match(m.group(1), m.group(2))

    if not intervals:
        for m in RE_DATE_RANGE.finditer(search_section):
            process_match(m.group(1), m.group(2))

    if not intervals:
        return None

    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged: List[List[int]] = [[sorted_intervals[0][0], sorted_intervals[0][1]]]
    for cur_s, cur_e in sorted_intervals[1:]:
        prev = merged[-1]
        if cur_s <= prev[1]:
            prev[1] = max(prev[1], cur_e)
        else:
            merged.append([cur_s, cur_e])

    total_months = sum((e - s) for s, e in merged if e > s)
    completed_years = total_months // 12
    remaining_months = total_months % 12

    if completed_years <= 0 and remaining_months <= 0:
        return None
    if completed_years <= 0:
        unit = 'month' if remaining_months == 1 else 'months'
        return f"{remaining_months} {unit}"
    if remaining_months == 0:
        unit = 'year' if completed_years == 1 else 'years'
        return f"{completed_years} {unit}"
    return f"{completed_years}.{remaining_months} years"


def parse_numeric_years(s: str) -> Optional[int]:
    if not s:
        return None
    m = compile_re(r'(\d+)\s*(?:months?|mos?)', 'i').search(s)
    if m and not compile_re(r'years?|yrs?', 'i').search(s):
        months = int(m.group(1))
        return months // 12

    ym = compile_re(r'(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr\b)', 'i').search(s)
    if ym and ym.group(1):
        return math.floor(float(ym.group(1)))

    num = compile_re(r'(\d+(?:\.\d+)?)').search(s)
    if num and num.group(1):
        return math.floor(float(num.group(1)))

    return None


parseNumericYears = parse_numeric_years

RE_TOTAL_EXP_DIRECT = compile_re(
    r'^((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))$',
    'i'
)
RE_SURROUNDING_RELEVANT = compile_re(r'\brelevant\s+experience\b', 'i')
RE_PRECEDING_RELEVANT = compile_re(r'\brelevant\s*$', 'i')
RE_OVERALL_TOTAL = compile_re(r'\b(?:overall|total)\b', 'i')
RE_FOLLOWING_DEGREE = compile_re(r'^\s*(?:degree|course|b\.?tech|b\.?e|m\.?tech|m\.?e|diploma|graduation)\b', 'i')

EXP_LABELED_PATTERNS = [
    {
        're': compile_re(
            r'(?:^|[|\n\r;•*▪▫❖➢✓★-])\s*(?:(?:total|overall)\s+(?:work\s+|professional\s+|industry\s+|it\s+|software\s+)?(?:years\s+of\s+)?(?:experience|exp\.?)|(?:total\s+)?years\s+of\s+experience)\s*(?:is|of)?\s*(?:[:|\t\-–—]\s*|\s*\n\s*|\s{2,})((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))',
            'gi'
        ),
        'isTotal': True,
    },
    {
        're': compile_re(
            r'(?:^|[|\n\r;•*▪▫❖➢✓★-])\s*(?:(?:work|professional)\s+(?:experience|exp\.?)|experience|exp\.?)\s*(?:is|of)?\s*(?:[:|\t\-–—]\s*|\s*\n\s*|\s{2,})((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))',
            'gi'
        ),
        'isTotal': False,
    },
]

EXP_SENTENCE_TOTAL_PATTERNS = [
    compile_re(
        r'\b((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))\s+(?:of\s+)?(?:overall|total)\s*(?:work\s+|professional\s+|industry\s+|it\s+|software\s+)?experience\b',
        'gi'
    ),
    compile_re(
        r'\b(?:overall|total)\s+(?:work\s+|professional\s+|industry\s+|it\s+|software\s+)?experience\s*(?:is|of|[:\-–—])?\s*((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))',
        'gi'
    ),
]

EXP_SENTENCE_GENERAL_PATTERNS = [
    compile_re(
        r'\b((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))\s+(?:of\s+)?(?:work\s+|professional\s+|industry\s+|it\s+|software\s+|technical\s+|hands[- ]on\s+|rich\s+|extensive\s+|proven\s+|progressive\s+|successful\s+|diverse\s+|practical\s+)?(?:career\s+)?experience\b',
        'gi'
    ),
    compile_re(
        r'\b(?:having|with|offering|bringing|possessing)\s+((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))\s+(?:of\s+)?(?:[a-zA-Z\-]+\s+)?experience\b',
        'gi'
    ),
]


def extract_total_experience_info(text: str) -> Dict[str, Any]:
    if not text or not js_trim(text):
        return {'text': '', 'years': None}

    s = js_trim(text)

    direct_match = RE_TOTAL_EXP_DIRECT.search(s)
    if direct_match and direct_match.group(1) and js_trim(direct_match.group(1)):
        cleaned = cleanExperienceOutput(js_trim(direct_match.group(1)))
        if cleaned:
            return {'text': cleaned, 'years': parse_numeric_years(cleaned)}

    class CandidateRecord:
        def __init__(self, raw: str, cleaned: str, years: Optional[int], score: int, index: int):
            self.raw = raw
            self.cleaned = cleaned
            self.years = years
            self.score = score
            self.index = index

    candidates: List[CandidateRecord] = []

    def add_candidate(raw_snippet: str, match_idx: int, score: int):
        surrounding = s[max(0, match_idx - 35): match_idx + len(raw_snippet) + 35]
        preceding = s[max(0, match_idx - 35): match_idx]
        if RE_SURROUNDING_RELEVANT.search(surrounding) or RE_PRECEDING_RELEVANT.search(preceding):
            if not RE_OVERALL_TOTAL.search(surrounding) and not RE_OVERALL_TOTAL.search(raw_snippet):
                return

        after_idx = match_idx + len(raw_snippet)
        following = s[after_idx: min(len(s), after_idx + 30)]
        if RE_FOLLOWING_DEGREE.search(following):
            return

        cleaned = cleanExperienceOutput(raw_snippet)
        if not cleaned:
            return

        candidates.append(CandidateRecord(
            raw=raw_snippet,
            cleaned=cleaned,
            years=parse_numeric_years(cleaned),
            score=score,
            index=match_idx,
        ))

    for item in EXP_LABELED_PATTERNS:
        for m in item['re'].finditer(s):
            grp = m.group(1)
            if grp and js_trim(grp):
                add_candidate(js_trim(grp), m.start(), 100 if item['isTotal'] else 85)

    for cre in EXP_SENTENCE_TOTAL_PATTERNS:
        for m in cre.finditer(s):
            grp = m.group(1)
            if grp and js_trim(grp):
                add_candidate(js_trim(grp), m.start(), 95)

    for cre in EXP_SENTENCE_GENERAL_PATTERNS:
        for m in cre.finditer(s):
            grp = m.group(1)
            if grp and js_trim(grp):
                add_candidate(js_trim(grp), m.start(), 70)

    if not candidates:
        return {'text': '', 'years': None}

    candidates.sort(key=lambda c: (-c.score, c.index))

    best = candidates[0]
    best_score = best.score
    top_candidates = [c for c in candidates if c.score == best_score]

    plus_cand = next((c for c in top_candidates if '+' in c.cleaned), None)
    if plus_cand:
        base_num = compile_re(r'\+.*$').sub('', plus_cand.cleaned)
        non_plus_match = next(
            (c for c in top_candidates if '+' not in c.cleaned and c.cleaned.startswith(base_num)),
            None
        )
        if non_plus_match:
            return {'text': plus_cand.cleaned, 'years': plus_cand.years}

    winner = top_candidates[0]
    return {'text': winner.cleaned, 'years': winner.years}


def extract_relevant_experience(text: str) -> Optional[str]:
    return ""


RE_CURRENT_COMPANY_LABELED = compile_re(
    r'(?:current\s+(?:company|organization|employer)|present\s+(?:company|organization|employer)|'
    r'currently\s+working\s+(?:at|in|with)|presently\s+working\s+(?:at|in|with)|'
    r'current\s+workplace|organization|company|employer)\s*[:\-]\s*([^\n]{2,120})',
    'i'
)
RE_CURRENT_COMPANY_1 = compile_re(r'currently\s+i\s+am\s+working\s+as\s+[^.\n]{0,40}\s+in\s+([A-Za-z][A-Za-z0-9&.\- ]{2,80})', 'i')
RE_CURRENT_COMPANY_2 = compile_re(r'currently\s+working\s+(?:as\s+[^.\n]{0,40}\s+)?at\s+([A-Za-z][A-Za-z0-9&.\- ]{2,80})', 'i')
RE_CURRENT_COMPANY_3 = compile_re(r'presently\s+working\s+with\s+([A-Za-z][A-Za-z0-9&.\- ]{2,80})', 'i')
RE_CLEAN_TRAILING_PUNCT = compile_re(r'[.,;:]+$')


def extract_current_company(text: str) -> Optional[str]:
    labeled = RE_CURRENT_COMPANY_LABELED.search(text)
    if labeled and labeled.group(1):
        v = js_trim(compile_re(r'\s+', 'g').sub(' ', labeled.group(1)))
        v = js_trim(compile_re(r'\(.*?\)|[-–—]\s*(?:present|current|\d{4}).*$', 'i').sub('', v))
        v = RE_CLEAN_TRAILING_PUNCT.sub('', v)
        if v and len(v) >= 2 and not compile_re(r'^(?:not\s+specified|n/a|none)$', 'i').search(v):
            return v

    exp_co_match = compile_re(
        r'(?:company\s+name|current\s+employer|client\s+name)\s*[:\-]\s*([A-Za-z0-9&.\- ]{2,80})',
        'i'
    ).search(text)
    if exp_co_match and exp_co_match.group(1):
        v = RE_CLEAN_TRAILING_PUNCT.sub('', js_trim(compile_re(r'\s+', 'g').sub(' ', exp_co_match.group(1))))
        if v and len(v) >= 2:
            return v

    for pattern in [RE_CURRENT_COMPANY_1, RE_CURRENT_COMPANY_2, RE_CURRENT_COMPANY_3]:
        m = pattern.search(text)
        if m and m.group(1):
            val = RE_CLEAN_TRAILING_PUNCT.sub('', js_trim(compile_re(r'\s+', 'g').sub(' ', m.group(1))))
            if val:
                return val

    return None


RE_LOCATION_LABELED = compile_re(
    r'(?:current\s+location|preferred\s+location|location|based\s+in|city)\s*[:\-]\s*([^\n]{2,120})',
    'i'
)
RE_ADDRESS_LABELED = compile_re(
    r'(?:permanent\s+address|current\s+address|address)\s*[:\-]\s*([^\n]{2,140})',
    'i'
)
RE_CITY_IN_ADDR = compile_re(
    r'\b(Pune|Mumbai|Bengaluru|Bangalore|Hyderabad|Chennai|Delhi|Noida|Gurgaon|Gurugram|Kolkata|Ahmedabad|Vadodara|Jaipur|Indore|Coimbatore|Kochi|Trivandrum|Chandigarh|Nagpur|Bhubaneswar)\b',
    'i'
)
RE_STATE_IN_ADDR = compile_re(
    r'\b(Maharashtra|Karnataka|Tamil Nadu|Telangana|Andhra Pradesh|Kerala|Gujarat|Delhi|Uttar Pradesh|Madhya Pradesh|Rajasthan|West Bengal|Odisha|Punjab|Haryana)\b',
    'i'
)
RE_CITY_STATE = compile_re(
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*,\s*(Maharashtra|Karnataka|Tamil Nadu|Telangana|Andhra Pradesh|Kerala|Gujarat|Delhi|Uttar Pradesh|Madhya Pradesh|Rajasthan|West Bengal|Odisha|Punjab|Haryana|Bihar|Chhattisgarh|Jharkhand|Assam|Goa)\b',
    'i'
)


def extract_current_location(text: str) -> Optional[str]:
    labeled = RE_LOCATION_LABELED.search(text)
    if labeled and labeled.group(1):
        v = js_trim(compile_re(r'\s+', 'g').sub(' ', labeled.group(1)))
        if v:
            return v

    address_match = RE_ADDRESS_LABELED.search(text)
    if address_match and address_match.group(1):
        addr = address_match.group(1)
        city_m = RE_CITY_IN_ADDR.search(addr)
        if city_m and city_m.group(1):
            state_m = RE_STATE_IN_ADDR.search(addr)
            return f"{city_m.group(1)}, {state_m.group(1)}" if state_m and state_m.group(1) else city_m.group(1)

    city_state = RE_CITY_STATE.search(text)
    if city_state and city_state.group(1) and city_state.group(2):
        city = js_trim(compile_re(r'\s+', 'g').sub(' ', city_state.group(1)))
        state = js_trim(compile_re(r'\s+', 'g').sub(' ', city_state.group(2)))
        return f"{city}, {state}"

    return None


ROLE_NOUNS_REGEX = compile_re(
    r'\b(?:Consultant|Engineer|Developer|Architect|Analyst|Specialist|Lead|Manager|Administrator|'
    r'Tester|Designer|Programmer|Scientist|Coordinator|Technician|Officer|Executive|Auditor|'
    r'Professional|Expert|Practitioner|Associate|Generalist|Recruiter|Strategist|Director|'
    r'Inspector|Supervisor|Operator|Surveyor|Mechanic|Electrician|Fitter|Machinist)\b',
    'i'
)

PROFESSIONAL_DOMAINS_REGEX = compile_re(
    r'\b(?:Global\s+Mobility(?:\s+Immigration)?|Immigration|Human\s+Resources|Talent\s+Acquisition|'
    r'Business\s+Intelligence|Data\s+Science|Data\s+Analytics|Machine\s+Learning|Artificial\s+Intelligence|'
    r'Cloud\s+Computing|DevOps|Cyber\s+Security|Information\s+Security|Network\s+Engineering|'
    r'Quality\s+Assurance|UI/UX(?:\s+Design)?|Digital\s+Marketing|Supply\s+Chain|Product\s+Management|'
    r'Project\s+Management)\b',
    'i'
)

RE_HEADLINE_SEPARATOR = compile_re(
    r'\s*\|\s*|\s*[•·*]\s*|\s*[–—]\s*|\s+--\s+|\s+-\s+|\s+/\s+|\s*,\s*(?=[A-Z])|\t+|\s{3,}'
)

RE_ROLE_STRIP_DATE = compile_re(
    r'\s*\((?:19|20)\d{2}[^)]*\)|\s*\((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^)]*\)|\s*[-–—|]\s*(?:(?:19|20)\d{2}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b.*$',
    'i'
)

RE_ROLE_REJECT_EDUCATION = compile_re(
    r'\b(?:graduate|post\s*graduate|fresher|undergraduate|alumnus|alumni)\b|'
    r'\b(?:bachelor|master|diploma|degree)\s+of\b|'
    r'\b(?:b\.?tech|b\.?e\.?|m\.?tech|m\.?e\.?|mca|bca|mba|bba|b\.?sc|m\.?sc|ph\.?d)\b',
    'i'
)

SENIORITY_PREFIXES = ('senior', 'lead', 'principal', 'staff', 'chief', 'head', 'associate', 'junior')


def check_seniority_upgrade(headline_role: str, summary_role: str) -> str:
    if not headline_role or not summary_role:
        return headline_role
    if any(headline_role.lower().startswith(p + ' ') for p in SENIORITY_PREFIXES):
        return headline_role
    matching_prefix = next((p for p in SENIORITY_PREFIXES if summary_role.lower().startswith(p + ' ')), None)
    if not matching_prefix:
        return headline_role
    norm_head = set(headline_role.lower().replace('software', '').split())
    norm_sum = set(summary_role.lower().replace(matching_prefix, '').replace('software', '').split())
    if norm_head and norm_sum and (norm_head.issubset(norm_sum) or norm_sum.issubset(norm_head)):
        return summary_role
    return headline_role


def to_title_case_phrase(str_val: str) -> str:
    lowercase_words = {'and', 'or', 'of', 'in', 'the', 'for', 'with', 'to', 'at', 'by', '&'}
    normalized = compile_re(r'\s*,\s*', 'g').sub(', ', str_val)
    normalized = js_trim(compile_re(r'\s+', 'g').sub(' ', normalized))

    words = js_split_whitespace(normalized)
    out_words: List[str] = []
    for i, word in enumerate(words):
        has_comma = word.endswith(',')
        w = word[:-1] if has_comma else word
        lower = w.lower()
        if i > 0 and lower in lowercase_words:
            out_words.append(lower + (',' if has_comma else ''))
        else:
            cap = (w[0].upper() + w[1:]) if w else ''
            out_words.append(cap + (',' if has_comma else ''))

    return ' '.join(out_words)


RE_ROLE_STRIP_PUNCT_START = compile_re(r'^[\s•\-–—*.,;:|]+')
RE_ROLE_STRIP_PUNCT_END = compile_re(r'[\s.,;:!|]+$')
RE_ROLE_REJECT_HEADING = compile_re(
    r'^(?:internship|internships|projects?|education|academics?|certifications?|strengths?|'
    r'technical\s+skills|key\s+skills|core\s+skills|skills|core\s+competencies|competencies|'
    r'professional\s+summary|career\s+summary|profile\s+summary|executive\s+summary|personal\s+summary|'
    r'technical\s+summary|summary\s+of\s+qualifications?|summary|executive\s+profile|career\s+profile|'
    r'professional\s+overview|profile|objective|career\s+objective|about\s+me|synopsis|'
    r'work\s+experience|professional\s+experience|employment\s+history|work\s+history|employment|experience|'
    r'achievements?|key\s+achievements?|accomplishments?|awards?|languages?|declaration|references?|'
    r'personal\s+details?|contact\s+details?|personal\s+profile|personal\s+information|resume|curriculum\s+vitae|biodata)\b',
    'i'
)
RE_ROLE_REJECT_STUDENT = compile_re(
    r'\b(?:intern|internship|trainee|student|graduate\s+assistant|research\s+assistant)\b',
    'i'
)
RE_ROLE_REJECT_DUTY = compile_re(
    r'^(?:worked|working|responsibilities|responsible|handled|handling)\b|'
    r'\b(?:developed|developing|designed\s+(?:machine|web|models?)|built|creating|implemented|managed|worked\s+(?:on|with|in|at|for)|working\s+(?:on|with|in|at|for)|responsible\s+for|responsibilities|the\s+project\s+development\s+process|gained\s+hands[- ]on|learned\s+the|improved\s+understanding|evaluation|attend(?:ed|ing)|participat(?:ed|ing)|conducted|prepared|tracked|facilitated|collaborated)\b',
    'i'
)
RE_ROLE_REJECT_MULTI_SENTENCE = compile_re(r'[.!?]\s+[A-Za-z]')

RE_ROLE_STRIP_EXP_1 = compile_re(
    r'\s*[-–—|:(,]\s*(?:over\s+|nearly\s+|about\s+|approximately\s+|more\s+than\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|months?|mos?)(?:\s+of\s+experience)?\)?.*$',
    'i'
)
RE_ROLE_STRIP_EXP_2 = compile_re(
    r'\s+(?:with|having|possessing|offering)\s+(?:over\s+|nearly\s+|about\s+|approximately\s+|more\s+than\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|months?|mos?).*$',
    'i'
)
RE_ROLE_STRIP_EXP_3 = compile_re(
    r'\s+(?:with|having|possessing|specializing\s+in|specialized\s+in|experienced\s+in|offering)\s+(?:experience\s+using|experience\s+in|background\s+in)\s+.*$',
    'i'
)
RE_ROLE_STRIP_EXP_4 = compile_re(r'\s*[-–—|]\s*\d+\+?\s*(?:years?|yrs?).*$', 'i')

RE_ROLE_REJECT_DURATION_ONLY = compile_re(
    r'^\s*(?:over\s+|nearly\s+|about\s+|approximately\s+|more\s+than\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|months?|mos?)\s*(?:of\s+experience)?\s*$',
    'i'
)
RE_ROLE_REJECT_YEARS_START = compile_re(r'^\s*\d+\+?\s*(?:years?|yrs?)\s+(?:of\s+)?', 'i')
RE_ROLE_REJECT_YEARS_IN = compile_re(r'\b\d+\s+years\b', 'i')
RE_ROLE_REJECT_WORKED_IN = compile_re(r'\b(?:worked\s+in|experience\s+in)\b.*\b\d+\s+years\b', 'i')
RE_ROLE_GENERIC_STANDALONE = compile_re(
    r'^(?:professional|expert|practitioner|associate|generalist|officer|executive|consultant|specialist|lead|manager|engineer|developer|analyst)$',
    'i'
)
RE_ROLE_DOMAIN_KEYWORDS = compile_re(
    r'\b(?:industry|sector|capital\s+equipment|storage\s+systems|operations)\b',
    'i'
)
RE_ROLE_DOMAIN_ACTIVITIES = compile_re(
    r'^(?:erection|pre[\s-]commissioning|commissioning|production\s+operations)',
    'i'
)

# Equipment / Instrument names that contain ROLE_NOUNS like "Tester" but are NOT job titles
RE_ROLE_REJECT_EQUIPMENT = compile_re(
    r'\b(?:Surface\s+Roughness|Roundness|Gear\s+Roll|Profile\s+Projector|Vision\s+Measuring|'
    r'Contour\s+Measuring|Hardness|Tensile|Impact|Vibration|Pressure|Temperature|'
    r'Coordinate\s+Measuring|Optical|Digital|Portable|Handheld)\s+'
    r'(?:Tester|Instrument|Machine|System|Equipment|Device|Meter|Gauge)\b',
    'i'
)

# Map domain/discipline phrases (commonly found in headlines) to proper role titles
_DOMAIN_TO_ROLE_MAP = [
    (compile_re(r'^quality\s+engineering$', 'i'), 'Quality Engineer'),
    (compile_re(r'^quality\s+inspection$', 'i'), 'Quality Inspector'),
    (compile_re(r'^quality\s+assurance$', 'i'), 'Quality Assurance Engineer'),
    (compile_re(r'^quality\s+control$', 'i'), 'Quality Control Engineer'),
    (compile_re(r'^software\s+engineering$', 'i'), 'Software Engineer'),
    (compile_re(r'^data\s+engineering$', 'i'), 'Data Engineer'),
    (compile_re(r'^data\s+analysis$', 'i'), 'Data Analyst'),
    (compile_re(r'^data\s+science$', 'i'), 'Data Scientist'),
    (compile_re(r'^business\s+analysis$', 'i'), 'Business Analyst'),
    (compile_re(r'^business\s+intelligence$', 'i'), 'Business Intelligence Analyst'),
    (compile_re(r'^mechanical\s+design(?:\s+engineering)?$', 'i'), 'Mechanical Design Engineer'),
    (compile_re(r'^network\s+engineering$', 'i'), 'Network Engineer'),
    (compile_re(r'^devops(?:\s+engineering)?$', 'i'), 'DevOps Engineer'),
    (compile_re(r'^cloud\s+(?:computing|engineering)$', 'i'), 'Cloud Engineer'),
    (compile_re(r'^cyber\s+security$', 'i'), 'Cyber Security Engineer'),
    (compile_re(r'^information\s+security$', 'i'), 'Information Security Engineer'),
    (compile_re(r'^ui/?ux\s+design$', 'i'), 'UI/UX Designer'),
    (compile_re(r'^digital\s+marketing$', 'i'), 'Digital Marketing Specialist'),
    (compile_re(r'^product\s+management$', 'i'), 'Product Manager'),
    (compile_re(r'^project\s+management$', 'i'), 'Project Manager'),
    (compile_re(r'^supply\s+chain(?:\s+management)?$', 'i'), 'Supply Chain Manager'),
    (compile_re(r'^human\s+resources$', 'i'), 'HR Professional'),
    (compile_re(r'^talent\s+acquisition$', 'i'), 'Talent Acquisition Specialist'),
    (compile_re(r'^(?:first\s+article\s+inspection|fai)$', 'i'), 'Quality Inspector'),
]


def _convert_domain_to_role(phrase: str) -> Optional[str]:
    """Convert a domain/discipline phrase to a proper professional role title."""
    p = js_trim(phrase)
    if not p:
        return None
    for regex, role_title in _DOMAIN_TO_ROLE_MAP:
        if regex.search(p):
            return role_title
    return None


def _validate_single_role_phrase(c: str) -> Optional[str]:
    c = js_trim(c)
    if not c or len(c) < 3 or len(c) > 100:
        return None

    if is_actual_section_heading_line(c) or RE_SECTION_HEADING.search(c) or RE_ROLE_REJECT_HEADING.search(c):
        return None
    if RE_ROLE_REJECT_STUDENT.search(c):
        return None
    if RE_ROLE_REJECT_DUTY.search(c):
        return None
    if RE_ROLE_REJECT_MULTI_SENTENCE.search(c):
        return None
    if RE_ROLE_REJECT_EDUCATION.search(c):
        return None
    if RE_ROLE_REJECT_EQUIPMENT.search(c):
        return None

    c = compile_re(r'[\U00010000-\U0010ffff\u2600-\u27ff]+').sub('', c)
    c = js_trim(c)
    c = RE_ROLE_STRIP_DATE.sub('', c)
    c = RE_ROLE_STRIP_EXP_1.sub('', c)
    c = RE_ROLE_STRIP_EXP_2.sub('', c)
    c = RE_ROLE_STRIP_EXP_3.sub('', c)
    c = RE_ROLE_STRIP_EXP_4.sub('', c)
    c = js_trim(c)

    if (
        RE_ROLE_REJECT_DURATION_ONLY.search(c)
        or RE_ROLE_REJECT_YEARS_START.search(c)
        or RE_ROLE_REJECT_YEARS_IN.search(c)
        or RE_ROLE_REJECT_WORKED_IN.search(c)
    ):
        return None

    if isCertificationOrNonAcademic(c):
        return None

    if RE_ROLE_GENERIC_STANDALONE.search(c):
        return None

    is_recognized_domain = (
        bool(PROFESSIONAL_DOMAINS_REGEX.search(c))
        or bool(RE_ROLE_DOMAIN_KEYWORDS.search(c))
        or bool(RE_ROLE_DOMAIN_ACTIVITIES.search(c))
    )

    if is_recognized_domain:
        if len([w for w in js_split_whitespace(c) if w]) <= 10:
            return to_title_case_phrase(c)

    if not ROLE_NOUNS_REGEX.search(c):
        return None

    if len([w for w in js_split_whitespace(c) if w]) > 5:
        return None

    if ',' in c:
        return None

    return to_title_case_phrase(c)


def clean_and_validate_role_or_technologies(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    c = js_trim(RE_ROLE_STRIP_PUNCT_END.sub('', RE_ROLE_STRIP_PUNCT_START.sub('', raw)))
    if not c or len(c) < 3 or len(c) > 100:
        return None
    if is_actual_section_heading_line(c) or RE_SECTION_HEADING.search(c) or RE_ROLE_REJECT_HEADING.search(c):
        return None

    direct = _validate_single_role_phrase(c)
    if direct:
        return direct

    if RE_HEADLINE_SEPARATOR.search(c):
        segments = [js_trim(s) for s in RE_HEADLINE_SEPARATOR.split(c) if js_trim(s)]
        for seg in segments:
            val = _validate_single_role_phrase(seg)
            if val:
                return val

    return None


cleanAndValidateDesignation = clean_and_validate_role_or_technologies


def slice_section_content(text: str, heading_regex: Any) -> Optional[str]:
    re_pat = compile_re(
        f"(?:^|\\n)\\s*{heading_regex.pattern}\\s*[:\\-]?(?:\\s*\\n|\\s+)([\\s\\S]*?)(?=\\n\\s*(?:Education|Academic|Technical\\s+Skills|Technologies|Skills|Core\\s+Skills|Key\\s+Skills|Core\\s+Competencies|Competencies|Experience|Professional\\s+Experience|Work\\s+Experience|Employment|Equipment(?:\\s+Handled)?|Software\\s+Skills|Tools|Additional\\s+Information|Projects?|Certifications?|Declaration|Personal|Contact)\\b|$)",
        'i'
    )
    m = re_pat.search(text)
    return js_trim(m.group(1)) if m and m.group(1) else None


RE_SENIORITY = compile_re(r'\b(Senior|Lead|Principal|Junior|Associate|Staff)\b', 'i')


def infer_role_from_narrative_context(chunk: str) -> Optional[str]:
    if not chunk or len(chunk) < 8:
        return None

    if compile_re(r'^(?:seeking|looking|aspiring)\b', 'i').search(chunk):
        return None

    sen_m = RE_SENIORITY.search(chunk)
    seniority = sen_m.group(1).capitalize() if sen_m else None

    # 1. Inspection (Quality Inspector, In-Process Inspector, CMM Inspector)
    insp_m = compile_re(
        r'\b(?:experience\s+(?:in|with)|background\s+in|expertise\s+in|skilled\s+in|specializing\s+in|worked\s+in|proficient\s+in)\s+'
        r'(?:[A-Za-z0-9\s-]{0,25}\s+)?(?:quality\s+inspection|in[\s-]process\s+inspection|cmm\s+inspection|mechanical\s+inspection|final\s+inspection)\b',
        'i'
    ).search(chunk)
    if insp_m:
        base = "Quality Inspector"
        res = f"{seniority} {base}" if seniority and seniority.lower() not in base.lower() else base
        return clean_and_validate_role_or_technologies(res)

    # 2. Quality Engineering / Control / Assurance
    qa_m = compile_re(
        r'\b(?:experience\s+(?:in|with)|background\s+in|expertise\s+in|skilled\s+in|specializing\s+in|worked\s+in|proficient\s+in)\s+'
        r'(?:[A-Za-z0-9\s-]{0,25}\s+)?(?:quality\s+(?:control|engineering|assurance)|qa\s+(?:engineering|testing)|software\s+testing)\b',
        'i'
    ).search(chunk)
    if qa_m:
        base = "Quality Engineer"
        res = f"{seniority} {base}" if seniority and seniority.lower() not in base.lower() else base
        return clean_and_validate_role_or_technologies(res)

    # 3. Development / Engineering
    dev_m = compile_re(
        r'\b(?:experience\s+(?:in|with)|background\s+in|expertise\s+in|skilled\s+in|specializing\s+in|worked\s+in|proficient\s+in)\s+'
        r'(?:(?:the\s+)?([A-Za-z0-9#+.\s-]{1,30}?)\s*(?:application\s+|software\s+|web\s+|systems?\s+)?(?:development|programming|engineering)|'
        r'developing\s+([A-Za-z0-9#+.\s-]{1,30}?)\s*(?:applications?|software|systems?))\b',
        'i'
    ).search(chunk)
    if dev_m:
        tech = js_trim(dev_m.group(1) or dev_m.group(2) or '')
        tech = compile_re(r'^(?:all\s+phases\s+of|modern|enterprise|scalable|robust|complex|full\s+lifecycle|end[\s-]to[\s-]end|various|different)\s+', 'i').sub('', tech)
        tech = js_trim(tech)
        if tech and not compile_re(r'^(?:various|different|multiple|new|high|best|and)$', 'i').search(tech):
            clean_tech = to_title_case_phrase(tech)
            clean_tech = compile_re(r'\bDotnet\b', 'i').sub('.NET', clean_tech)
            base = f"{clean_tech} Developer" if clean_tech.lower() not in ('software', 'web') else f"{clean_tech} Developer"
        else:
            base = "Software Developer"
        res = f"{seniority} {base}" if seniority and seniority.lower() not in base.lower() else base
        return clean_and_validate_role_or_technologies(res)

    # 4. Data Analysis / Business Analysis
    da_m = compile_re(
        r'\b(?:experience\s+(?:in|with)|background\s+in|expertise\s+in|skilled\s+in|specializing\s+in|worked\s+in|proficient\s+in)\s+'
        r'(?:[A-Za-z0-9\s-]{0,20}\s+)?(data\s+analysis|business\s+analysis)\b',
        'i'
    ).search(chunk)
    if da_m:
        kind = da_m.group(1).lower()
        base = "Data Analyst" if 'data' in kind else "Business Analyst"
        res = f"{seniority} {base}" if seniority and seniority.lower() not in base.lower() else base
        return clean_and_validate_role_or_technologies(res)

    # 5. Data Engineering / Data Science
    data_m = compile_re(
        r'\b(?:experience\s+(?:in|with)|background\s+in|expertise\s+in|skilled\s+in|specializing\s+in|worked\s+in|proficient\s+in)\s+'
        r'(?:[A-Za-z0-9\s-]{0,20}\s+)?(data\s+engineering|data\s+science)\b',
        'i'
    ).search(chunk)
    if data_m:
        kind = data_m.group(1).lower()
        base = "Data Engineer" if 'engineering' in kind else "Data Scientist"
        res = f"{seniority} {base}" if seniority and seniority.lower() not in base.lower() else base
        return clean_and_validate_role_or_technologies(res)

    # 6. Mechanical Design
    md_m = compile_re(
        r'\b(?:experience\s+(?:in|with)|background\s+in|expertise\s+in|skilled\s+in|specializing\s+in|worked\s+in|proficient\s+in)\s+'
        r'mechanical\s+design(?:\s+engineering)?\b',
        'i'
    ).search(chunk)
    if md_m:
        base = "Mechanical Design Engineer"
        res = f"{seniority} {base}" if seniority and seniority.lower() not in base.lower() else base
        return clean_and_validate_role_or_technologies(res)

    # 7. Administration
    admin_m = compile_re(
        r'\b(?:experience\s+(?:in|with)|background\s+in|expertise\s+in|skilled\s+in|specializing\s+in|worked\s+in|proficient\s+in)\s+'
        r'(database|system|systems|network|linux|windows|cloud)\s+administration\b',
        'i'
    ).search(chunk)
    if admin_m:
        kind = admin_m.group(1).lower()
        if kind == 'database':
            base = "Database Administrator"
        elif kind in ('system', 'systems', 'linux', 'windows'):
            base = "System Administrator"
        elif kind == 'network':
            base = "Network Administrator"
        elif kind == 'cloud':
            base = "Cloud Administrator"
        else:
            base = "System Administrator"
        res = f"{seniority} {base}" if seniority and seniority.lower() not in base.lower() else base
        return clean_and_validate_role_or_technologies(res)

    # 8. Architecture
    arch_m = compile_re(
        r'\b(?:experience\s+(?:in|with)|background\s+in|expertise\s+in|skilled\s+in|specializing\s+in|worked\s+in|proficient\s+in)\s+'
        r'(cloud|solutions?|enterprise|software|system)\s+architecture\b',
        'i'
    ).search(chunk)
    if arch_m:
        kind = arch_m.group(1).lower()
        if kind == 'cloud':
            base = "Cloud Architect"
        elif 'solution' in kind:
            base = "Solutions Architect"
        elif kind == 'enterprise':
            base = "Enterprise Architect"
        else:
            base = "Software Architect"
        res = f"{seniority} {base}" if seniority and seniority.lower() not in base.lower() else base
        return clean_and_validate_role_or_technologies(res)

    return None


def extract_role_from_narrative(content: Optional[str]) -> Optional[str]:
    if not content:
        return None
    chunks = [
        js_trim(s)
        for s in compile_re(r'\r?\n|[.;]').split(content)
        if js_trim(s)
    ]
    # Pass 1: Explicit designation stated in chunk
    for chunk in chunks:
        if not chunk or len(chunk) < 3:
            continue
        if compile_re(r'^(?:seeking|looking|aspiring)\b', 'i').search(chunk):
            continue

        s = compile_re(r'^(?:(?:professional|career|profile|executive)?\s*summary|profile|objective)\s*[:\-]\s*', 'i').sub('', chunk)
        s = compile_re(r'^(?:(?:working|experience|employed|role|serving)\s+as\s+(?:an?|the)?)\s*', 'i').sub('', s)
        s = compile_re(r'^(?:(?:over|around|having)?\s*[\d+.]+\s+years(?:\s+of)?\s+experience\s+(?:in\s+the\s+industry\s+)?as\s+(?:an?|the)?)\s*', 'i').sub('', s)
        s = compile_re(r'^(?:experienced|results?-driven|dynamic|accomplished|skilled|certified|energetic|seasoned|passionate|innovative|motivated)\s+', 'i').sub('', s)
        s = js_trim(s)

        split_match = compile_re(
            r'\s+(?:with|having|possessing|specialized\s+in|specializing\s+in|experienced\s+in|offering|bringing|seeking|looking\s+for|in\s+building|skilled\s+in|proven\s+track|dedicated\s+to|proficient\s+in)\b',
            'i'
        ).split(s)
        candidate_str = js_trim(split_match[0]) if split_match else s

        candidate_str = js_trim(compile_re(r'\s+(?:professional|expert|practitioner)\s*$', 'i').sub('', candidate_str))
        if compile_re(r'^(?:professional|expert|practitioner|associate|generalist|officer|executive)$', 'i').search(candidate_str):
            continue

        if RE_ROLE_REJECT_EDUCATION.search(candidate_str) or DEGREE_RE.search(candidate_str):
            continue

        validated = clean_and_validate_role_or_technologies(candidate_str)
        if validated:
            return validated

        # Try domain-to-role conversion on compound phrases (e.g. "Quality Engineering and Quality Inspection" -> "Quality Engineer")
        compound_parts = [js_trim(p) for p in compile_re(r'\s+(?:and|&)\s+', 'i').split(candidate_str) if js_trim(p)]
        for part in compound_parts:
            converted = _convert_domain_to_role(part)
            if converted:
                return converted

    # Pass 2: Contextual identification from stated experience in summary
    for chunk in chunks:
        inferred = infer_role_from_narrative_context(chunk)
        if inferred:
            return inferred

    return None


def is_actual_section_heading_line(line: str) -> bool:
    s = js_trim(compile_re(r'^[\s•\-–—*#:|]+').sub('', line))
    s = js_trim(compile_re(r'[\s•\-–—*#:|]+$').sub('', s))
    if not s:
        return False
    if RE_SECTION_HEADING.search(s):
        return True
    kw = r'(?:skills?|technical\s+skills?|key\s+skills?|core\s+competencies|competencies|professional\s+experience|work\s+experience|experience|employment(?:\s+history)?|education|academic|projects?|certifications?|declaration|summary)'
    if compile_re(r'^(?:' + kw + r')\b', 'i').search(s) and len(s) < 80:
        return True
    parts = [js_trim(compile_re(r'^[\s•\-–—*#:]+').sub('', p)) for p in s.split('|') if js_trim(p)]
    if len(parts) >= 2 and all(bool(compile_re(r'^(?:' + kw + r')\b', 'i').search(p)) for p in parts):
        return True
    tab_parts = [js_trim(p) for p in compile_re(r'\t+|\s{3,}').split(s) if js_trim(p)]
    if len(tab_parts) >= 2 and any(bool(compile_re(r'^(?:' + kw + r')\b', 'i').search(p)) for p in tab_parts):
        return True
    return False


def extract_role_from_headline(text: str) -> Optional[str]:
    header_lines = split_lines(text)[:15]
    candidate_name = extract_name(header_lines, text)
    domain_converted_role = None  # Track first domain-to-role conversion as fallback
    for raw_line in header_lines:
        line = js_trim(compile_re(r'^[\s•\-–—*]+').sub('', raw_line))
        if not line or len(line) < 3 or len(line) > 120:
            continue
        if (
            is_actual_section_heading_line(line)
            or compile_re(r'^(?:professional\s+summary|career\s+summary|profile\s+summary|summary|objective|profile|experience|skills|education)\s*[:\-]', 'i').search(line)
        ):
            break
        if compile_re(r'^(?:worked|working|responsibilities|responsible|handled|handling)\b', 'i').search(line):
            continue

        if candidate_name and line.lower() == candidate_name.lower():
            continue

        # Split composite headline lines into segments (e.g. "Quality Inspector – In-Process & Final Inspection | Aerospace")
        segments = [js_trim(s) for s in RE_HEADLINE_SEPARATOR.split(line) if js_trim(s)]
        candidates = segments if segments else [line]

        for cand in candidates:
            # Skip pure contact, address, or name tokens within composite lines
            if compile_re(r'@|https?://|www\.|\.com\b', 'i').search(cand):
                continue
            if compile_re(r'\b(?:phone|mobile|tel|cell|email|contact|linkedin|github)\b', 'i').search(cand):
                continue
            if compile_re(r'^\+?\d[\d\s\-()]{7,}\d$').search(cand):
                continue
            if compile_re(r'^(?:hyderabad|bangalore|bengaluru|mumbai|pune|delhi|chennai|kolkata|noida|gurgaon|new york|london|san francisco|california|texas|india|usa|uk)[,\s]', 'i').search(cand):
                continue
            if compile_re(r'^[A-Za-z\s]+,\s*[A-Za-z\s]+(?:\s+\d{5,6})?$').search(cand):
                continue
            if candidate_name and cand.lower() == candidate_name.lower():
                continue

            title_split = compile_re(r'\s+(?:with|having)\s+[0-9]', 'i').split(cand)
            cand_clean = js_trim(title_split[0]) if title_split else cand

            # Priority A: Direct role validation (e.g. "Quality Inspector", "Senior Java Developer")
            validated = clean_and_validate_role_or_technologies(cand_clean)
            if validated:
                return validated

            # Priority B: Domain phrase to role conversion (e.g. "QUALITY ENGINEERING" -> "Quality Engineer")
            if domain_converted_role is None:
                converted = _convert_domain_to_role(cand_clean)
                if converted:
                    domain_converted_role = converted

    # If no direct role was found but we have a domain-to-role conversion, use it
    if domain_converted_role:
        return domain_converted_role

    return None


def extract_role_from_employment(text: str, current_company: Optional[str] = None) -> Optional[str]:
    labeled = compile_re(
        r'(?:^|\n)\s*(?:current\s+designation|current\s+role|current\s+position|designation|current\s+job\s+title|job\s+title|role)\s*[:\-]\s*([^\n]+)',
        'i'
    ).search(text)
    if labeled and labeled.group(1):
        validated = clean_and_validate_role_or_technologies(labeled.group(1))
        if validated:
            return validated

    exp_match = compile_re(
        r'\n\s*(?:Professional\s+Experience|Work\s+Experience|Work\s+History|Employment\s+History|Career\s+History|Experience|Employment)\s*:?\s*\n([\s\S]{20,4000}?)(?=\n\s*(?:Education|Technical\s+Skills|Skills|Projects?|Certifications?)\b|$)',
        'i'
    ).search(text)
    if exp_match and exp_match.group(1):
        exp_lines = split_lines(exp_match.group(1))[:30]
        for raw_line in exp_lines:
            line = js_trim(compile_re(r'^[\s•\-–—*]+').sub('', raw_line))
            if not line or len(line) > 100:
                continue
            if compile_re(r'^(?:responsibilities|roles|duties|project|client|tools|team|environment|duration)\b', 'i').search(line):
                continue
            before_at = js_trim(compile_re(r'\s+(?:at|in|with|-|–|—|\|)\s+', 'i').split(line)[0])
            check_candidate = before_at if before_at and len(before_at) >= 3 else line
            validated = clean_and_validate_role_or_technologies(check_candidate)
            if validated:
                return validated

    return None


def format_activity_phrase(raw: str) -> str:
    parts = [
        js_trim(s)
        for s in compile_re(r'[,;&]|\band\b', 'i').split(raw)
        if js_trim(s)
    ]
    normalized_parts: List[str] = []
    for part in parts:
        p = js_trim(part)
        p_lower = p.lower()
        if p_lower in ('pre-commissioning', 'pre commissioning'):
            normalized_parts.append('Pre-commissioning')
        elif p_lower == 'erection':
            normalized_parts.append('Erection')
        elif p_lower == 'commissioning':
            normalized_parts.append('Commissioning')
        elif p_lower in ('production operation', 'production operations'):
            normalized_parts.append('Production Operations')
        elif p_lower == 'procurement':
            normalized_parts.append('Procurement')
        elif p_lower == 'fabrication':
            normalized_parts.append('Fabrication')
        elif p_lower == 'installation':
            normalized_parts.append('Installation')
        elif p_lower == 'maintenance':
            normalized_parts.append('Maintenance')
        else:
            normalized_parts.append(to_title_case_phrase(p))

    if len(normalized_parts) <= 1:
        return normalized_parts[0] if normalized_parts else ''
    last = normalized_parts[-1]
    rest = normalized_parts[:-1]
    return f"{', '.join(rest)} and {last}"


RE_INDUSTRY_MATCH = compile_re(
    r'\b(?:experience\s+in|background\s+in|domain\s+of|field\s+of)\s+([A-Za-z0-9\s,&/\'-]+?\s*(?:industry|sector|domain|field))\b',
    'i'
)
RE_SPEC_MATCH = compile_re(
    r'\b(?:specializing|specialized|expertise)\s+in\s+([A-Za-z0-9\s,&/\'-]+?)(?:\s+(?:with|having|offering)\b|[.;\n]|$)',
    'i'
)
RE_ACTIVITIES_MATCH = compile_re(
    r'\b(?:worked\s+experience\s+in|experience\s+in|activities\s+in|hands-on\s+in)\s+((?:erection|pre[\s-]commissioning|commissioning|production\s+operations?|procurement|fabrication|installation|maintenance|design\s+and\s+drafting|product\s+development|simulation)[A-Za-z0-9\s,&/\'-]*?)(?:\s+(?:of|for|at|in|with)\b|[.;\n]|$)',
    'i'
)


def extract_domain_or_industry_from_text(content: Optional[str]) -> Optional[str]:
    if not content:
        return None

    industry_match = RE_INDUSTRY_MATCH.search(content)
    if industry_match and industry_match.group(1):
        raw = js_trim(industry_match.group(1))
        if 5 <= len(raw) <= 100 and not compile_re(r'\b(?:responsible|working|proven|track\s+record)\b', 'i').search(raw):
            return to_title_case_phrase(raw)

    spec_match = RE_SPEC_MATCH.search(content)
    if spec_match and spec_match.group(1):
        raw = js_trim(spec_match.group(1))
        if (
            5 <= len(raw) <= 100
            and not compile_re(r'\b(?:responsible|working)\b', 'i').search(raw)
            and not compile_re(r'\b(?:uk|germany|usa?|india|canada|australia|singapore|uae|dubai|europe|asia|america)\b', 'i').search(raw)
        ):
            formatted = compile_re(r'\s+and\s+', 'gi').sub(', ', raw)
            return to_title_case_phrase(formatted)

    activities_match = RE_ACTIVITIES_MATCH.search(content)
    if activities_match and activities_match.group(1):
        raw = js_trim(activities_match.group(1))
        if 5 <= len(raw) <= 100:
            return format_activity_phrase(raw)

    return None


def extract_verbatim_designation(text: str, current_company: Optional[str] = None) -> Optional[str]:
    # PRIORITY 1: Explicit designation near candidate's name (Header / Headline)
    role_headline = extract_role_from_headline(text)

    # PRIORITY 2: Professional Summary / Summary / Profile / Career Summary / About Me
    summary_sections = [
        {'name': 'Professional Summary', 'content': slice_section_content(text, compile_re(r'Professional\s+Summary', 'i')) or ''},
        {'name': 'Executive Profile', 'content': slice_section_content(text, compile_re(r'Executive\s+Profile', 'i')) or ''},
        {'name': 'Profile Summary', 'content': slice_section_content(text, compile_re(r'Profile\s+Summary', 'i')) or ''},
        {'name': 'Career Summary', 'content': slice_section_content(text, compile_re(r'Career\s+Summary', 'i')) or ''},
        {'name': 'Career Profile', 'content': slice_section_content(text, compile_re(r'Career\s+Profile', 'i')) or ''},
        {'name': 'Professional Overview', 'content': slice_section_content(text, compile_re(r'Professional\s+Overview', 'i')) or ''},
        {'name': 'Summary of Qualifications', 'content': slice_section_content(text, compile_re(r'Summary\s+of\s+Qualifications?', 'i')) or ''},
        {'name': 'Summary', 'content': slice_section_content(text, compile_re(r'(?<!Professional\s+|Career\s+|Profile\s+)Summary', 'i')) or ''},
        {'name': 'Profile', 'content': slice_section_content(text, compile_re(r'(?<!Executive\s+|Profile\s+)(?:Professional\s+)?Profile', 'i')) or ''},
        {'name': 'About Me', 'content': slice_section_content(text, compile_re(r'About\s+Me', 'i')) or ''},
        {'name': 'Objective', 'content': slice_section_content(text, compile_re(r'(?:Career\s+)?Objective', 'i')) or ''},
    ]
    summary_sections = [s for s in summary_sections if js_trim(s['content'])]

    if role_headline:
        # Check summary for seniority upgrade if it refers to the exact same role (e.g. Full Stack Engineer -> Senior Full Stack Engineer)
        for sec in summary_sections:
            sec_role = extract_role_from_narrative(sec['content'])
            if sec_role:
                role_headline = check_seniority_upgrade(role_headline, sec_role)
                break
        return role_headline

    for sec in summary_sections:
        role = extract_role_from_narrative(sec['content'])
        if role:
            validated = clean_and_validate_role_or_technologies(role)
            if validated:
                return validated

    # Domain / Industry activity fallback in summary (for legacy summary phrasing)
    for sec in summary_sections:
        domain_or_activity = extract_domain_or_industry_from_text(sec['content'])
        if domain_or_activity:
            validated = clean_and_validate_role_or_technologies(domain_or_activity)
            if validated:
                return validated

    # FALLBACK: If no role is found in header or summary, return None.
    # NEVER fall back to the Experience / Work Experience section.
    return None


def extract_skills_from_eligible_block(skills_block: str) -> List[str]:
    candidates = extractDeterministicSkills(skills_block)
    res_val = validateSkillsAgainstSection(candidates, skills_block, 10)
    return res_val['validSkills']


def extract_whole_resume_skills(full_text: str, technical_block: Optional[str] = None) -> List[str]:
    if technical_block and js_trim(technical_block):
        from_block = extract_skills_from_eligible_block(technical_block)
        if from_block:
            return from_block
    result = extractSkillsWithEngineSync(full_text)
    return result['skills']


def parse_core_fields_from_resume_text(raw_text: str) -> CoreParsedFields:
    text = (
        raw_text
        .replace('\r\n', '\n')
        .replace('\r', '\n')
    )
    text = compile_re(r'[\u200B-\u200D\uFEFF]', 'g').sub('', text)
    lines = split_lines(text)

    email = extract_email(text)
    phone = extract_phone(text)
    linkedin = extract_linkedin(text)
    name = extract_name(lines, text)

    edu_block = slice_education_block(text)
    edu_pick = pick_best_education_from_block(edu_block)
    highest_qualification = edu_pick['highestQualification']
    any_qual = extract_highest_qualification_from_any_text(text)

    if not highest_qualification:
        highest_qualification = any_qual
    elif any_qual:
        r_pick = rank_line_for_degree(highest_qualification)
        r_any = rank_line_for_degree(any_qual)
        if r_any > r_pick or (r_any == r_pick and len(any_qual) > len(highest_qualification) and len(any_qual) <= 80):
            highest_qualification = any_qual

    if highest_qualification and compile_re(r'^(description|roles?|team\s*size|duration|customer|tools?)\b', 'i').search(highest_qualification):
        highest_qualification = None

    education_items = edu_pick['educationItems']
    if not highest_qualification:
        sparse = extract_education_items(edu_block)
        degree_line = next(
            (e for e in sparse if DEGREE_RE.search(e) and not isCertificationOrNonAcademic(e)),
            None
        )
        if degree_line:
            highest_qualification = cleanAcademicSpecialization(degree_line)
            if not education_items and highest_qualification:
                education_items = [highest_qualification]

    if highest_qualification:
        highest_qualification = cleanAcademicSpecialization(highest_qualification) or highest_qualification

    if education_items:
        clean_edu = [sanitizeDisplayText(e) for e in education_items if sanitizeDisplayText(e)][:2]
        education_raw = ', '.join(clean_edu) if clean_edu else None
    else:
        education_raw = None

    tech_block = slice_technical_skills_block(text)
    skill_list = extract_whole_resume_skills(text, tech_block)
    skills_raw = ', '.join(skill_list) if skill_list else None
    verbatim_role = extract_verbatim_designation(text)
    exp_info = extract_total_experience_info(text)
    relevant_experience = extract_relevant_experience(text)
    current_company = extract_current_company(text)
    current_location = extract_current_location(text)

    sanitized_role = sanitizeDisplayText(verbatim_role) if verbatim_role else None

    return {
        'candidateName': sanitizeDisplayText(name) if name else None,
        'email': email,
        'contactNumber': phone,
        'linkedinUrl': linkedin,
        'highestQualification': sanitizeDisplayText(highest_qualification) if highest_qualification else None,
        'educationRaw': education_raw,
        'skillsRaw': skills_raw,
        'technologiesRaw': sanitized_role,
        'technologies': sanitized_role,
        'totalExperienceYears': exp_info['years'],
        'totalExperienceText': exp_info['text'],
        'relevantExperience': relevant_experience or None,
        'currentCompany': sanitizeDisplayText(current_company) if current_company else None,
        'currentLocation': sanitizeDisplayText(current_location) if current_location else None,
        'role': sanitized_role,
    }


# Aliases matching JS export names
parseCoreFieldsFromResumeText = parse_core_fields_from_resume_text
extractEligibleSkillsBlock = extract_eligible_skills_block
extractTotalExperienceInfo = extract_total_experience_info
extractWholeResumeSkills = extract_whole_resume_skills
extractVerbatimDesignation = extract_verbatim_designation
calculateExperienceFromWorkHistory = calculate_experience_from_work_history
extractHighestQualificationFromAnyText = extract_highest_qualification_from_any_text
extractCurrentLocation = extract_current_location
cleanAndValidateRoleOrTechnologies = clean_and_validate_role_or_technologies
