"""
Normalize parsed résumé field text for DB/UI (no stray periods, clean education).
"""
from typing import Optional
from src.jsRegex import compile_re, js_trim, js_split_whitespace

MONTH = 'january|february|march|april|may|june|july|august|september|october|november|december'

RE_NBSP = compile_re(r'\u00a0', 'g')
RE_WS = compile_re(r'\s+', 'g')
RE_TRAILING_PUNCT = compile_re(r'[.!?;:]+$', 'g')
RE_DANGLING_IN = compile_re(r'\s+in\s*$', 'i')
RE_DANGLING_FROM = compile_re(r'\s+from\s*$', 'i')
RE_DANGLING_AT = compile_re(r'\s+at\s*$', 'i')

RE_SKILL_PREFIX = compile_re(r'^[\s•\-–—*]+')
RE_SKILL_CAT_PREFIX = compile_re(
    r'^(?:Core|Technical|Primary|Secondary|Key|Other|Tools?|Languages?|Platforms?|Databases?|Frameworks?|Cloud)\s*:\s*',
    'i'
)
RE_INITIAL = compile_re(r'\b[A-Z]\.', 'g')
RE_PUNCT_CHECK = compile_re(r'[.!?]')

CERTIFICATION_STOP_RE = compile_re(
    r'\b(?:scrum\s*master|master\s*trainer|master\s*of\s*ceremonies|pmp|prince2|itil|'
    r'six\s*sigma|istqb|ceh|cisp|cissp|cisa|aws\s+certified|azure\s+administrator|'
    r'google\s+(?:cloud\s+)?certified|cisco\s+certified|ccna|ccnp|oracle\s+certified|'
    r'certified\s+solutions|certified\s+developer|certified\s+administrator|'
    r'professional\s+certificate|training\s+certificate|online\s+course|bootcamp|'
    r'course\s+completion)\b',
    'i'
)

RE_CERT_CHECK = compile_re(r'\b(?:certified|certification|certificate|training|workshop|bootcamp|license|licence)\b', 'i')
RE_DEGREE_CHECK = compile_re(r'\b(?:degree|diploma|b\.?\s*tech|m\.?\s*tech|bachelor|master|doctorate|ph\.?\s*d)\b', 'i')

DEGREE_RE = compile_re(
    r'\b(?:B\.?\s*Tech(?:\s*\(Hons\))?|M\.?\s*Tech|B\.?\s*E\.?|M\.?\s*E\.?|B\.?\s*S(?:\b|\.)|'
    r'M\.?\s*S(?:\b|\.)|B\.?\s*Sc\.?|M\.?\s*Sc\.?|B\.?\s*Com\.?|M\.?\s*Com\.?|B\.?\s*A(?:\b|\.)|'
    r'M\.?\s*A(?:\b|\.)|B\.?\s*Arch|M\.?\s*Arch|MCA|MBA|PGDM|PGDCA|Post\s+Graduate\s+Diploma|'
    r'BBA|BCA|B\.?\s*Pharm|M\.?\s*Pharm|Diploma(?:\s+in\s+[A-Za-z&/]+(?:\s+[A-Za-z&/]+){0,3})?|'
    r'Polytechnic|Ph\.?\s*D|Doctorate|Doctor\s+of\s+Philosophy|'
    r'Bachelor(?:\'s)?(?:\s+of\s+[A-Za-z&/]+(?:\s+[A-Za-z&/]+){0,3})?(?:\s+(?:in|with)\s+[A-Za-z&/]+(?:\s+[A-Za-z&/]+){0,4})?|'
    r'Master(?:\'s)?(?:\s+of\s+[A-Za-z&/]+(?:\s+[A-Za-z&/]+){0,3})?(?:\s+(?:in|with)\s+[A-Za-z&/]+(?:\s+[A-Za-z&/]+){0,4})?|'
    r'Associate(?:\s+Degree)?(?:\s+of\s+[A-Za-z&/]+(?:\s+[A-Za-z&/]+){0,3})?)\b',
    'i'
)

RE_TABLE_ROW_NUM = compile_re(r'^\d+[\s.)\-–—]+')
RE_NARRATIVE_MARKERS = compile_re(
    r'^(?:completed\s+)?(?:degree\s+in|qualification\s+in|graduation\s+in|graduated\s+from|'
    r'pursuing\s+(?:a\s+)?|completed\s+|holds\s+a\s+|highest\s+qualification\s*[:\-]?\s*)\s*',
    'i'
)
RE_LOOKBEHIND_PERIOD_CUT = compile_re(r'(?<!\b(?:[A-Z]|Tech|Engg|Hons|Phil|Admin))\.\s+[\s\S]*', 'i')
RE_NARRATIVE_CLAUSES_1 = compile_re(
    r'\b(?:currently|presently)?\s*(?:working|employed|serving|holding\s+(?:a|the)\s+(?:position|role)|'
    r'reporting\s+to|managing\s+a\s+team)\b[\s\S]*',
    'i'
)
RE_NARRATIVE_CLAUSES_2 = compile_re(
    r'\b(?:with|having|possessing)\s+(?:over\s+|nearly\s+|about\s+|more\s+than\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|months?)\b[\s\S]*',
    'i'
)
RE_NARRATIVE_CLAUSES_3 = compile_re(r'\b\d+(?:\.\d+)?\+?\s*(?:years?|yrs?)\s+of\s+experience\b[\s\S]*', 'i')
RE_TRAILING_JOB_ROLES = compile_re(
    r'\s*[-–—|,/]?\s*(?:currently\s+)?(?:working\s+as\s+)?(?:Technical\s+Lead|Software\s+Engineer|'
    r'Senior\s+Engineer|Developer|Lead\s+Developer|Solution\s+Architect|Team\s+Lead|Project\s+Manager|'
    r'Manager|Analyst|Consultant|Specialist|Administrator|Coordinator|Executive|Officer|Director)\b[\s\S]*',
    'i'
)
RE_CGPA = compile_re(r'\b(?:cgpa|sgpa|gpa)\s*[:\-]?\s*[\d.]+\s*(?:\/\s*\d+)?\b', 'gi')
RE_PERCENTAGE_1 = compile_re(r'\b(?:percentage|aggregate|marks?|scores?)\s*[:\-]?\s*[\d.]+\s*%?\b', 'gi')
RE_PERCENTAGE_2 = compile_re(r'\b\d+(?:\.\d+)?\s*%\b', 'g')
RE_DISTINCTION = compile_re(r'\b(?:distinction|first\s*class|second\s*class|with\s+honou?rs)\b', 'gi')
RE_YEAR_RANGE = compile_re(r'\s*[,;]?\s*(?:19|20)\d{2}\s*[-–]\s*(?:19|20)\d{2}\b', 'g')
RE_SINGLE_YEAR = compile_re(r'\s*[,;]?\s*\b(?:19|20)\d{2}\b', 'g')

RE_INSTITUTION_1 = compile_re(r'\s+(?:from|at|affiliated\s+to|accredited\s+by)\s+[\s\S]*', 'i')
RE_INSTITUTION_2 = compile_re(
    r'\s*[,;–—\-]\s*[A-Za-z0-9&.\'\s-]{2,50}\s+(?:University|College|Institute|School|Academy|Board|'
    r'Vidyapeeth|Campus|Technologies|Solutions|Services|Pvt\s+Ltd|Ltd|Inc)\b[\s\S]*',
    'i'
)
RE_INSTITUTION_3 = compile_re(
    r'\s{2,}[A-Za-z0-9&.\'\s-]{2,50}\s+(?:University|College|Institute|School|Academy|Board|Vidyapeeth|Campus)\b[\s\S]*',
    'i'
)
RE_INSTITUTION_4 = compile_re(
    r'\s+(?!(?:Mechanical|Electrical|Civil|Computer|Chemical|Aerospace|Biomedical|Information|'
    r'Software|Automobile|Electronics|Production|Industrial)\b)[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\s+'
    r'(?:University|College|Institute|Vidyapeeth)\b[\s\S]*',
    'i'
)
RE_INSTITUTION_5 = compile_re(
    r'\b(?:University|College|Institute|School|Academy)\s+(?:of\s+)?[A-Z][A-Za-z0-9&.\'\s-]{2,80}\b',
    'i'
)

RE_TRAILING_PUNCT_EDU = compile_re(r'[.,;:·\-–—]+$', 'g')
RE_POST_DEGREE_INST = compile_re(r'\s+(?:from|at|in\s+university|in\s+college|affiliated\s+to|accredited\s+by)\b[\s\S]*', 'i')
RE_POST_DEGREE_WORK_1 = compile_re(r'\b(?:currently|presently)?\s*(?:working|employed|serving|holding\s+(?:a|the)\s+(?:position|role))\b[\s\S]*', 'i')
RE_POST_DEGREE_WORK_2 = compile_re(
    r'\s*[-–—|,/]?\s*(?:currently\s+)?(?:working\s+as\s+)?(?:Technical\s+Lead|Software\s+Engineer|'
    r'Senior\s+Engineer|Developer|Lead\s+Developer|Solution\s+Architect|Team\s+Lead|Project\s+Manager|'
    r'Manager|Analyst|Consultant|Specialist)\b[\s\S]*',
    'i'
)
RE_TRAILING_DEGREE_PUNCT = compile_re(r'[,;:\-–—\s.]+$')

RE_ROLE_KEYWORD = compile_re(r'\b(?:consultant|engineer|developer|architect|analyst|specialist|manager|lead)\b', 'i')
RE_SAP_SF = compile_re(r'\bsap\s+successfactors\b', 'i')
RE_CONSULTANT = compile_re(r'\bconsultant\b', 'i')


def sanitize_display_text(raw: Optional[str]) -> str:
    if raw is None:
        raw = ''
    t = str(raw)
    t = RE_NBSP.sub(' ', t)
    t = RE_WS.sub(' ', t)
    t = js_trim(t)
    if not t:
        return ''
    t = js_trim(RE_TRAILING_PUNCT.sub('', t))
    # Dangling preposition only
    t = RE_DANGLING_IN.sub('', t)
    t = RE_DANGLING_FROM.sub('', t)
    t = RE_DANGLING_AT.sub('', t)
    return js_trim(RE_WS.sub(' ', t))


def normalize_skill_token(raw: str) -> str:
    t = sanitize_display_text(raw)
    if not t:
        return ''
    t = RE_SKILL_PREFIX.sub('', t)
    t = RE_SKILL_CAT_PREFIX.sub('', t)
    stripped = RE_INITIAL.sub('', t)
    if RE_PUNCT_CHECK.search(stripped):
        return ''
    return js_trim(t)


def is_certification_or_non_academic(text: Optional[str]) -> bool:
    t = js_trim(str(text or ''))
    if not t:
        return False
    if compile_re(r'\bcertificate\s+of\s+sponsorship\b', 'i').search(t):
        return False
    if CERTIFICATION_STOP_RE.search(t):
        return True
    if RE_CERT_CHECK.search(t):
        if not RE_DEGREE_CHECK.search(t):
            return True
    return False


def clean_academic_specialization(raw: Optional[str]) -> Optional[str]:
    t = sanitize_display_text(raw)
    if not t:
        return None
    if is_certification_or_non_academic(t):
        return None

    # 1. Strip leading table row serial numbers (e.g. "1. ", "1) ", "• ")
    t = js_trim(RE_TABLE_ROW_NUM.sub('', t))

    # 2. Remove leading narrative markers
    t = RE_NARRATIVE_MARKERS.sub('', t)

    # 3. Cut off at period if preceded by a full word
    t = RE_LOOKBEHIND_PERIOD_CUT.sub('', t)

    # 4. Cut off narrative employment/experience clauses
    t = RE_NARRATIVE_CLAUSES_1.sub('', t)
    t = RE_NARRATIVE_CLAUSES_2.sub('', t)
    t = RE_NARRATIVE_CLAUSES_3.sub('', t)

    # 5. Cut off trailing job roles / designations
    t = RE_TRAILING_JOB_ROLES.sub('', t)

    # 6. Strip marks, CGPA, percentages
    t = RE_CGPA.sub(' ', t)
    t = RE_PERCENTAGE_1.sub(' ', t)
    t = RE_PERCENTAGE_2.sub(' ', t)
    t = RE_DISTINCTION.sub(' ', t)

    # 7. Strip years and year ranges
    t = RE_YEAR_RANGE.sub(' ', t)
    t = RE_SINGLE_YEAR.sub(' ', t)

    # 8. Strip institutions, colleges, and universities
    t = RE_INSTITUTION_1.sub(' ', t)
    t = RE_INSTITUTION_2.sub(' ', t)
    t = RE_INSTITUTION_3.sub(' ', t)
    t = RE_INSTITUTION_4.sub(' ', t)
    t = RE_INSTITUTION_5.sub(' ', t)

    # 9. Clean whitespace and trailing punctuation
    t = js_trim(RE_TRAILING_PUNCT_EDU.sub('', RE_WS.sub(' ', t)))
    if not t:
        return None

    # 10. Locate the degree token
    deg_match = DEGREE_RE.search(t)
    if not deg_match:
        return None

    # Extract from the degree token onwards
    degree_with_branch = js_trim(t[deg_match.start():])

    # 11. Repeat post-degree cutoffs on degreeWithBranch
    degree_with_branch = RE_LOOKBEHIND_PERIOD_CUT.sub('', degree_with_branch)
    degree_with_branch = RE_POST_DEGREE_INST.sub('', degree_with_branch)
    degree_with_branch = RE_POST_DEGREE_WORK_1.sub('', degree_with_branch)
    degree_with_branch = js_trim(RE_POST_DEGREE_WORK_2.sub('', degree_with_branch))

    # 12. Clean trailing punctuation
    degree_with_branch = js_trim(RE_TRAILING_DEGREE_PUNCT.sub('', degree_with_branch))

    # 13. Clean and format informal degree phrases (e.g. "Diploma mechanical engineer" -> "Diploma in Mechanical Engineering")
    m_diploma = compile_re(
        r'^(Diploma)\s+(?:in\s+)?(Mechanical|Civil|Electrical|Electronics|Automobile|Computer(?:\s+Science)?|Chemical|Aeronautical|Production|Instrumentation)\s+(?:engineer(?:ing)?)\b',
        'i'
    ).search(degree_with_branch)
    if m_diploma:
        deg = m_diploma.group(1).title()
        branch = m_diploma.group(2).title()
        degree_with_branch = f"{deg} in {branch} Engineering"

    return degree_with_branch if len(degree_with_branch) >= 2 else None


def compact_highest_qualification(raw: Optional[str]) -> Optional[str]:
    return clean_academic_specialization(raw)


def looks_like_job_role_phrase(token: str) -> bool:
    t = js_trim(token)
    if not t or len(t) < 8:
        return False
    words = [w for w in js_split_whitespace(t) if w]
    if RE_ROLE_KEYWORD.search(t) and 2 <= len(words) <= 8:
        return True
    if RE_SAP_SF.search(t) and RE_CONSULTANT.search(t):
        return True
    return False


# Aliases for JS export names
sanitizeDisplayText = sanitize_display_text
normalizeSkillToken = normalize_skill_token
isCertificationOrNonAcademic = is_certification_or_non_academic
cleanAcademicSpecialization = clean_academic_specialization
compactHighestQualification = compact_highest_qualification
looksLikeJobRolePhrase = looks_like_job_role_phrase

