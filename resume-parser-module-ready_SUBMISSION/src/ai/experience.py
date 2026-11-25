"""
Experience calculation, cleanup, and normalization logic.
"""
from typing import Any, Dict, List, Optional, Tuple
import datetime
import math
from src.jsRegex import compile_re, js_trim, js_round
from src.clock import get_current_utc_date

MONTHS: Dict[str, int] = {
    'jan': 0, 'january': 0, 'feb': 1, 'february': 1, 'mar': 2, 'march': 2,
    'apr': 3, 'april': 3, 'may': 4, 'jun': 5, 'june': 5, 'jul': 6, 'july': 6,
    'aug': 7, 'august': 7, 'sep': 8, 'sept': 8, 'september': 8,
    'oct': 9, 'october': 9, 'nov': 10, 'november': 10, 'dec': 11, 'december': 11,
}

RE_ISO_DATE = compile_re(r'^(\d{4})-(\d{1,2})$')
RE_YEAR_ONLY = compile_re(r'^(\d{4})$')
RE_NAMED_DATE = compile_re(r'([a-z]+)\s*[\',]?\s*(\d{4})')
RE_REVERSED_DATE = compile_re(r'(\d{4})\s*[-/]\s*([a-z]+)')

RE_LEADING_CHARS = compile_re(r'^[|:;\-–—•*▪▫❖➢✓★+\t\s]+')
RE_PREFIX_EXP = compile_re(
    r'^(?:(?:total|overall|work|professional)\s+)?(?:years\s+of\s+)?(?:experience|exp\.?)\s*(?:is|of)?\s*[:|\t\-–—]\s*',
    'i'
)
RE_PREFIX_QUALIFIER = compile_re(
    r'^(?:having\s+)?(?:experience\s+of\s+)?(?:nearly|approximately|approx|about|over|more\s+than|at\s+least|around|almost|totally|close\s+to|upwards\s+of|in\s+excess\s+of)\s+',
    'i'
)
RE_QUALIFIER_WORDS = compile_re(
    r'\b(?:overall|nearly|approximately|approx|about|over|more\s+than|having|experience\s+of|at\s+least|around|almost|totally|close\s+to|upwards\s+of|in\s+excess\s+of)\b',
    'gi'
)
RE_SUFFIX_EXP = compile_re(
    r'\s+(?:of\s+)?(?:overall|total|professional|work|industry|technical|it|software)?\s*experience.*$',
    'i'
)
RE_WS = compile_re(r'\s+', 'g')
RE_YEARS_AND_MONTHS = compile_re(
    r'^(\d+(?:\.\d+)?\+?)\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?(\d+)\s*(?:months?|mos?))?',
    'i'
)
RE_MONTHS_ONLY = compile_re(r'^(\d+)\s*(?:months?|mos?)', 'i')

RE_DIRECT_MATCH = compile_re(
    r'^((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))$',
    'i'
)

RE_PRECEDING_RELEVANT = compile_re(r'\brelevant\s*$', 'i')
RE_PRECEDING_RELEVANT_EXP = compile_re(r'\brelevant\s+experience\b', 'i')
RE_OVERALL_OR_TOTAL = compile_re(r'\b(?:overall|total)\b', 'i')
RE_FOLLOWING_EDU = compile_re(r'^\s*(?:degree|course|b\.?tech|b\.?e|m\.?tech|m\.?e|diploma|graduation)\b', 'i')

LABELED_PATTERNS = [
    {
        're': compile_re(
            r'(?:^|[|\n\r;•*▪▫❖➢✓★-])\s*(?:(?:total|overall)\s+(?:work\s+|professional\s+|industry\s+|it\s+|software\s+)?(?:years\s+of\s+)?(?:experience|exp\.?)|(?:total\s+)?years\s+of\s+experience)\s*(?:is|of)?\s*(?:[:|\t\-–—]\s*|\s*\n\s*|\s{2,})((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))',
            'gi'
        ),
        'score': 100,
    },
    {
        're': compile_re(
            r'(?:^|[|\n\r;•*▪▫❖➢✓★-])\s*(?:(?:work|professional)\s+(?:experience|exp\.?)|experience|exp\.?)\s*(?:is|of)?\s*(?:[:|\t\-–—]\s*|\s*\n\s*|\s{2,})((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))',
            'gi'
        ),
        'score': 85,
    },
]

SENTENCE_TOTAL_PATTERNS = [
    compile_re(
        r'\b((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))\s+(?:of\s+)?(?:overall|total)\s*(?:work\s+|professional\s+|industry\s+|it\s+|software\s+)?experience\b',
        'gi'
    ),
    compile_re(
        r'\b(?:overall|total)\s+(?:work\s+|professional\s+|industry\s+|it\s+|software\s+)?experience\s*(?:is|of|[:\-–—])?\s*((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))',
        'gi'
    ),
]

SENTENCE_GENERAL_PATTERNS = [
    compile_re(
        r'\b((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))\s+(?:of\s+)?(?:work\s+|professional\s+|industry\s+|it\s+|software\s+|technical\s+|hands[- ]on\s+|rich\s+|extensive\s+|proven\s+|progressive\s+|successful\s+|diverse\s+|practical\s+)?(?:career\s+)?experience\b',
        'gi'
    ),
    compile_re(
        r'\b(?:having|with|offering|bringing|possessing)\s+((?:(?:over|nearly|approx(?:imately)?|more\s+than|at\s+least|around|almost|about|close\s+to|upwards\s+of|in\s+excess\s+of)\s+)?\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|yr\b)(?:\s*(?:and\s*)?\d+\s*(?:months?|mos?))?|\d+\s*(?:months?|mos?))\s+(?:of\s+)?(?:[a-zA-Z\-]+\s+)?experience\b',
        'gi'
    ),
]

RE_PARSE_MONTHS_ONLY = compile_re(r'(\d+)\s*(?:months?|mos?)', 'i')
RE_PARSE_YM = compile_re(r'(\d+)\s*(?:years?|yrs?)\s+(\d+)\s*(?:months?|mos?)', 'i')
RE_PARSE_NUM = compile_re(r'(\d+(\.\d+)?)')


class PeriodDate:
    def __init__(
        self,
        date: Optional[datetime.datetime],
        is_present: bool,
        is_year_only: bool,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ):
        self.date = date
        self.isPresent = is_present
        self.isYearOnly = is_year_only
        self.year = year
        self.month = month


def parse_period_date(value: Any) -> Optional[PeriodDate]:
    if not value:
        return None
    raw = js_trim(str(value)).lower()
    if not raw or raw in ('present', 'current', 'now', 'till date', 'till now', 'ongoing'):
        return PeriodDate(date=None, is_present=True, is_year_only=False)

    iso = RE_ISO_DATE.search(raw)
    if iso and iso.group(1) and iso.group(2):
        y = int(iso.group(1))
        m = int(iso.group(2)) - 1
        return PeriodDate(date=None, is_present=False, is_year_only=False, year=y, month=m)

    year_only = RE_YEAR_ONLY.search(raw)
    if year_only and year_only.group(1):
        y = int(year_only.group(1))
        return PeriodDate(date=None, is_present=False, is_year_only=True, year=y)

    named = RE_NAMED_DATE.search(raw)
    if named and named.group(1) and named.group(2) and named.group(1) in MONTHS:
        return PeriodDate(
            date=None,
            is_present=False,
            is_year_only=False,
            year=int(named.group(2)),
            month=MONTHS[named.group(1)],
        )

    reversed_match = RE_REVERSED_DATE.search(raw)
    if (
        reversed_match
        and reversed_match.group(1)
        and reversed_match.group(2)
        and reversed_match.group(2) in MONTHS
    ):
        return PeriodDate(
            date=None,
            is_present=False,
            is_year_only=False,
            year=int(reversed_match.group(1)),
            month=MONTHS[reversed_match.group(2)],
        )

    return None


def calculate_experience_months(periods: Any) -> Optional[int]:
    if not isinstance(periods, list) or not periods:
        return None

    ranges: List[Tuple[int, int]] = []
    for p in periods:
        if not isinstance(p, dict):
            continue
        start_val = p.get('from') or p.get('start') or p.get('start_date')
        end_val = p.get('to') or p.get('end') or p.get('end_date')

        start = parse_period_date(start_val)
        end = parse_period_date(end_val)
        if not start or not end:
            continue

        is_year_only = start.isYearOnly and end.isYearOnly
        if is_year_only:
            if not end.year or not start.year or end.year < start.year:
                continue
            start_month = start.year * 12
            end_month = end.year * 12
        else:
            start_month = (start.year or 0) * 12 + (start.month or 0)
            if end.isPresent:
                now = get_current_utc_date()
                end_month = now.year * 12 + (now.month - 1)
            elif end.month is not None and end.year is not None:
                end_month = end.year * 12 + end.month + 1
            elif end.year is not None:
                end_month = end.year * 12 + 12
            else:
                continue

        if end_month < start_month:
            continue
        ranges.append((start_month, end_month))

    if not ranges:
        return None

    sorted_ranges = sorted(ranges, key=lambda r: r[0])
    merged: List[List[int]] = [[sorted_ranges[0][0], sorted_ranges[0][1]]]

    for cur_start, cur_end in sorted_ranges[1:]:
        prev = merged[-1]
        if cur_start <= prev[1]:
            prev[1] = max(prev[1], cur_end)
        else:
            merged.append([cur_start, cur_end])

    return sum(end - start for start, end in merged)


def clean_experience_output(raw: Any) -> str:
    if not raw or not isinstance(raw, str):
        return ''
    s = js_trim(raw)
    if not s:
        return ''

    s = RE_LEADING_CHARS.sub('', s)
    s = RE_PREFIX_EXP.sub('', s)
    s = RE_PREFIX_QUALIFIER.sub('', s)
    s = RE_QUALIFIER_WORDS.sub(' ', s)
    s = RE_SUFFIX_EXP.sub('', s)
    s = js_trim(RE_WS.sub(' ', s))

    m = RE_YEARS_AND_MONTHS.search(s)
    if m and m.group(1):
        num = m.group(1)
        unit = 'year' if num == '1' else 'years'
        if m.group(2):
            return f"{num} {unit} {m.group(2)} months"
        return f"{num} {unit}"

    m_month = RE_MONTHS_ONLY.search(s)
    if m_month and m_month.group(1):
        return f"{m_month.group(1)} months"

    return ''


def extract_stated_experience_wording(stated: Any) -> str:
    if not stated or not isinstance(stated, str):
        return ''
    s = js_trim(stated)
    if not s:
        return ''

    direct_match = RE_DIRECT_MATCH.search(s)
    if direct_match and direct_match.group(1) and js_trim(direct_match.group(1)):
        return clean_experience_output(js_trim(direct_match.group(1)))

    class Candidate:
        def __init__(self, raw: str, cleaned: str, score: int, index: int):
            self.raw = raw
            self.cleaned = cleaned
            self.score = score
            self.index = index

    candidates: List[Candidate] = []

    def add_candidate(raw_snippet: str, match_idx: int, score: int):
        start_idx = max(0, match_idx - 35)
        preceding = s[start_idx:match_idx]
        if RE_PRECEDING_RELEVANT.search(preceding) or RE_PRECEDING_RELEVANT_EXP.search(preceding):
            if not RE_OVERALL_OR_TOTAL.search(preceding) and not RE_OVERALL_OR_TOTAL.search(raw_snippet):
                return

        after_idx = match_idx + len(raw_snippet)
        following = s[after_idx:min(len(s), after_idx + 30)]
        if RE_FOLLOWING_EDU.search(following):
            return

        cleaned = clean_experience_output(raw_snippet)
        if not cleaned:
            return

        candidates.append(Candidate(raw=raw_snippet, cleaned=cleaned, score=score, index=match_idx))

    for item in LABELED_PATTERNS:
        cre = item['re']
        score = item['score']
        for m in cre.finditer(s):
            grp = m.group(1)
            if grp and js_trim(grp):
                add_candidate(js_trim(grp), m.start(), score)

    for cre in SENTENCE_TOTAL_PATTERNS:
        for m in cre.finditer(s):
            grp = m.group(1)
            if grp and js_trim(grp):
                add_candidate(js_trim(grp), m.start(), 95)

    for cre in SENTENCE_GENERAL_PATTERNS:
        for m in cre.finditer(s):
            grp = m.group(1)
            if grp and js_trim(grp):
                add_candidate(js_trim(grp), m.start(), 70)

    if not candidates:
        return ''

    # Sort descending by score, ascending by index (Python stable sort)
    candidates.sort(key=lambda c: (-c.score, c.index))

    best_score = candidates[0].score
    top_candidates = [c for c in candidates if c.score == best_score]

    plus_cand = next((c for c in top_candidates if '+' in c.cleaned), None)
    if plus_cand:
        base_num = compile_re(r'\+.*$').sub('', plus_cand.cleaned)
        non_plus_match = next(
            (c for c in top_candidates if '+' not in c.cleaned and c.cleaned.startswith(base_num)),
            None
        )
        if non_plus_match:
            return plus_cand.cleaned

    return top_candidates[0].cleaned


def parse_stated_years(raw: Any) -> Optional[int]:
    if not raw:
        return None
    s_raw = str(raw)
    m_only = RE_PARSE_MONTHS_ONLY.search(s_raw)
    if m_only and m_only.group(1):
        return int(m_only.group(1))

    ym = RE_PARSE_YM.search(s_raw)
    if ym and ym.group(1) and ym.group(2):
        return int(ym.group(1)) * 12 + int(ym.group(2))

    m = RE_PARSE_NUM.search(s_raw)
    if m and m.group(1):
        return js_round(float(m.group(1)) * 12.0)

    return None


def resolve_one_experience(stated: Optional[str]) -> Dict[str, Any]:
    if stated and isinstance(stated, str) and js_trim(stated):
        raw = js_trim(stated)
        display = extract_stated_experience_wording(raw)
        if display:
            total_months = parse_stated_years(display) or 0
            return {
                'display': display,
                'months': total_months,
                'years': js_round((total_months / 12.0) * 10.0) / 10.0,
                'yearsPart': total_months // 12,
                'monthsPart': total_months % 12,
            }

    return {
        'display': '',
        'months': 0,
        'years': 0,
        'yearsPart': 0,
        'monthsPart': 0,
    }


def resolve_experience_fields(
    total_experience: Optional[Any] = None,
    relevant_experience: Optional[Any] = None,
    work_periods: Optional[Any] = None,
    relevant_work_periods: Optional[Any] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    total = resolve_one_experience(total_experience)
    return {
        'total_experience': total['display'] or '',
        'total_experience_months': total['months'] or 0,
        'total_experience_years': total['years'] or 0,
        'relevant_experience': '',
        'relevant_experience_months': 0,
        'relevant_experience_years': 0,
    }


# Aliases for JS export names
calculateExperienceMonths = calculate_experience_months
cleanExperienceOutput = clean_experience_output
extractStatedExperienceWording = extract_stated_experience_wording
parseStatedYears = parse_stated_years
resolveOneExperience = resolve_one_experience
resolveExperienceFields = resolve_experience_fields

