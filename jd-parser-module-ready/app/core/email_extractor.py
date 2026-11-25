"""Universal Email Header Extraction Engine for JD Analyser.

Robustly extracts From, To, and CC fields (display names and email addresses)
across diverse email formats (Gmail, Outlook Web/Desktop, Apple Mail, multiline
headers, semicolon/comma variations).

Detects header boundaries to prevent email addresses in the JD body,
signatures, and disclaimers from being incorrectly assigned to From, To, or CC.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from email.utils import parseaddr
from typing import Any, Dict, List, Optional, Tuple

# RFC 5322 compatible email address pattern
EMAIL_REGEX = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    re.IGNORECASE,
)

# Known email header prefixes (case-insensitive)
HEADER_KEY_PATTERNS = [
    (r"^(?:from|sender|de|von)", "from"),
    (r"^(?:to|assigned\s*to|para|an)", "to"),
    (r"^(?:cc|copie|kopie)", "cc"),
    (r"^(?:bcc)", "bcc"),
    (r"^(?:sent|date|enviado\s*el|gesendet)", "date"),
    (r"^(?:subject|asunto|betreff)", "subject"),
]

# Section headers or salutations indicating the boundary between email headers and JD content
BODY_BOUNDARY_PATTERNS = [
    re.compile(r"^(?:hi|hello|dear|greetings|good\s+morning|good\s+afternoon|good\s+day)\b", re.I),
    re.compile(
        r"^(?:job\s*title|position(?:\s*title)?|role(?:\s*name)?|requirement(?:\s*#?\d+)?|about\s*(?:the\s*)?(?:role|job|us)|job\s*description|overview|responsibilities|qualifications|skills|requirements|key\s*skills|mandatory\s*skills)\s*[:\-–]",
        re.I,
    ),
    re.compile(r"^(?:[-–*=_\s]{3,})$"),
    re.compile(r"^(?:(?:[-*•+]|\d+\.)\s+)"),
]

FORWARD_DIVIDER_PATTERNS = [
    re.compile(r"^[-–_\s]*original\s+message[-–_\s]*$", re.I),
    re.compile(r"^[-–_\s]*forwarded\s+message[-–_\s]*$", re.I),
    re.compile(r"^_{10,}$"),
    re.compile(r"^-{10,}$"),
]


@dataclass
class EmailContact:
    """Structured representation of an email contact matching the API contract."""

    name: str = ""
    email: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "email": self.email}


@dataclass
class ExtractedEmailHeaders:
    """Complete result from universal email header extraction."""

    from_contacts: List[EmailContact] = field(default_factory=list)
    to_contacts: List[EmailContact] = field(default_factory=list)
    cc_contacts: List[EmailContact] = field(default_factory=list)
    bcc_contacts: List[EmailContact] = field(default_factory=list)
    subject: Optional[str] = None
    date: Optional[str] = None
    header_block: str = ""
    body_content: str = ""
    has_headers: bool = False

    def to_dict(self) -> Dict[str, List[Dict[str, str]]]:
        """Convert to the expected JSON output schema."""
        return {
            "from": [c.to_dict() for c in self.from_contacts],
            "to": [c.to_dict() for c in self.to_contacts],
            "cc": [c.to_dict() for c in self.cc_contacts],
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """Convert to the full schema including subject and date when present."""
        d: Dict[str, Any] = {
            "from": [c.to_dict() for c in self.from_contacts],
            "to": [c.to_dict() for c in self.to_contacts],
            "cc": [c.to_dict() for c in self.cc_contacts],
        }
        if self.subject:
            d["subject"] = self.subject
        if self.date:
            d["date"] = self.date
        return d


def normalize_email_text(raw_text: str) -> str:
    """Normalize Unicode newlines, spaces, quotes, and whitespace variations."""
    if not raw_text:
        return ""

    # Normalize carriage returns and Unicode line/paragraph separators to \n
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u2028", "\n").replace("\u2029", "\n").replace("\f", "\n")

    # Normalize Unicode spaces (non-breaking, zero-width, typographic) to ASCII space
    text = re.sub(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000\ufeff]", " ", text)
    text = re.sub(r"[\u200b\u200c\u200d]", "", text)

    # Normalize typographic quotation marks
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("«", '"').replace("»", '"')

    return text


def clean_display_name(name_raw: str, email_addr: str = "") -> str:
    """Clean display name by stripping quotes, mailto tags, and formatting artifacts."""
    if not name_raw:
        return ""

    s = name_raw.strip()

    # Remove enclosing quotes
    s = s.strip("\"' ")

    # Strip mailto: prefix if present
    s = re.sub(r"\[?\s*mailto:\s*", "", s, flags=re.I)
    s = s.strip("[]()<>\"' ")

    # Remove email address if embedded in display name
    if email_addr:
        s = s.replace(f"<{email_addr}>", "").replace(email_addr, "").strip()

    # Clean leading/trailing punctuation
    s = s.strip(" \t,:;–-")

    # If the name is just another email or equal to email_addr, clear it
    if EMAIL_REGEX.fullmatch(s) or (email_addr and s.lower() == email_addr.lower()):
        return ""

    # Collapse multiple spaces
    s = re.sub(r"\s+", " ", s).strip()

    # Handle Outlook "Last, First" personal names: "Smith, John" -> "John Smith"
    # Only if exactly two alphabetic parts separated by a comma (no corporate markers like Inc, LLC)
    if "," in s and not re.search(r"\b(?:inc|llc|ltd|corp|group|team|desk|services|solutions)\b", s, re.I):
        parts = [p.strip() for p in s.split(",")]
        if len(parts) == 2 and parts[0].replace(" ", "").isalpha() and parts[1].replace(" ", "").isalpha():
            s = f"{parts[1]} {parts[0]}"

    return s


def parse_single_recipient(raw_recipient: str) -> Optional[EmailContact]:
    """Parse a single recipient token into (name, email) with robust fallback heuristics."""
    token = raw_recipient.strip()
    if not token:
        return None

    # 1. Check for standard angle brackets: Name <email@domain.com>
    angle_match = re.search(r"<\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\s*>", token)
    if angle_match:
        email = angle_match.group(1).strip().lower()
        name_part = token[:angle_match.start()] + " " + token[angle_match.end():]
        name = clean_display_name(name_part, email)
        return EmailContact(name=name, email=email)

    # 2. Check for Outlook mailto format: Name [mailto:email@domain.com]
    mailto_match = re.search(
        r"\[\s*mailto:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\s*\]",
        token,
        re.IGNORECASE,
    )
    if mailto_match:
        email = mailto_match.group(1).strip().lower()
        name_part = token[:mailto_match.start()] + " " + token[mailto_match.end():]
        name = clean_display_name(name_part, email)
        return EmailContact(name=name, email=email)

    # 3. Check for parentheses format: Name (email@domain.com)
    paren_match = re.search(r"\(\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\s*\)", token)
    if paren_match:
        email = paren_match.group(1).strip().lower()
        name_part = token[:paren_match.start()] + " " + token[paren_match.end():]
        name = clean_display_name(name_part, email)
        return EmailContact(name=name, email=email)

    # 4. Standard Python email.utils.parseaddr fallback
    parsed_name, parsed_email = parseaddr(token)
    if parsed_email and EMAIL_REGEX.fullmatch(parsed_email):
        clean_name = clean_display_name(parsed_name, parsed_email)
        return EmailContact(name=clean_name, email=parsed_email.strip().lower())

    # 5. Regex search for any email inside the token
    email_search = EMAIL_REGEX.search(token)
    if email_search:
        email = email_search.group(0).strip().lower()
        name_part = token.replace(email_search.group(0), "")
        name = clean_display_name(name_part, email)
        return EmailContact(name=name, email=email)

    return None


def split_recipient_tokens(header_value: str) -> List[str]:
    """Split a recipient string into individual recipient tokens respecting quotes, angles, and delimiters.

    Uses semicolons as primary delimiter if present (standard in Outlook),
    otherwise splits on commas outside quotes and angle brackets.
    """
    if not header_value or not header_value.strip():
        return []

    val = header_value.strip()

    # Determine primary delimiter: if ';' is present, prefer ';'
    delimiter = ";" if ";" in val else ","

    tokens: List[str] = []
    current: List[str] = []
    in_angle = False
    in_bracket = False
    in_paren = False
    in_double_quote = False
    in_single_quote = False

    for char in val:
        if char == "<":
            in_angle = True
        elif char == ">":
            in_angle = False
        elif char == "[":
            in_bracket = True
        elif char == "]":
            in_bracket = False
        elif char == "(":
            in_paren = True
        elif char == ")":
            in_paren = False
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote

        is_delimiter = (
            char == delimiter
            and not in_angle
            and not in_bracket
            and not in_paren
            and not in_double_quote
            and not in_single_quote
        )

        if is_delimiter:
            token_str = "".join(current).strip()
            if token_str:
                tokens.append(token_str)
            current = []
        else:
            current.append(char)

    last_token = "".join(current).strip()
    if last_token:
        tokens.append(last_token)

    return tokens


def parse_recipient_list(header_value: str) -> List[EmailContact]:
    """Parse a full header value (potentially containing multiple recipients) into EmailContact objects."""
    tokens = split_recipient_tokens(header_value)

    # Merge comma-split unquoted "Last, First <email>" tokens
    merged_tokens: List[str] = []
    buffer = ""
    for token in tokens:
        if buffer:
            buffer = f"{buffer}, {token}"
        else:
            buffer = token

        if EMAIL_REGEX.search(buffer):
            merged_tokens.append(buffer)
            buffer = ""

    if buffer:
        merged_tokens.append(buffer)

    contacts: List[EmailContact] = []
    seen_emails: set[str] = set()

    for token in merged_tokens:
        contact = parse_single_recipient(token)
        if contact and contact.email:
            # Deduplicate by lowercase email while preserving order
            if contact.email not in seen_emails:
                seen_emails.add(contact.email)
                contacts.append(contact)

    return contacts


def match_header_key(line: str) -> Optional[Tuple[str, str]]:
    """Check if a line starts with a recognized email header key (e.g. 'From:', 'To:', 'Cc:').

    Returns (canonical_key, value) or None.
    Supported keys: from, to, cc, bcc, date, subject.
    """
    s = line.strip()
    if not s:
        return None

    for pattern, key in HEADER_KEY_PATTERNS:
        # Require a colon or dash delimiter after the header key
        match = re.match(pattern + r"\s*[:\-–]\s*(.*)$", s, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            return key, value

    return None


def is_body_boundary(line: str) -> bool:
    """Check if a line signifies the start of the job description body."""
    s = line.strip()
    if not s:
        return False

    for pat in BODY_BOUNDARY_PATTERNS:
        if pat.search(s):
            return True

    return False


def is_forward_divider(line: str) -> bool:
    """Check if a line is a forwarded message separator."""
    s = line.strip()
    return any(pat.match(s) for pat in FORWARD_DIVIDER_PATTERNS)


def extract_header_and_body_blocks(raw_text: str) -> Tuple[str, str, bool]:
    """Separate the email header block from the body content.

    Returns (header_text, body_text, has_headers).
    """
    normalized = normalize_email_text(raw_text)
    lines = normalized.split("\n")

    # Step 1: Scan for first header key
    start_idx: Optional[int] = None
    for idx, line in enumerate(lines):
        if is_forward_divider(line):
            continue
        if match_header_key(line):
            # If an email address appeared on a line BEFORE start_idx,
            # unlabelled headers precede this line
            if any(EMAIL_REGEX.search(prev_l) for prev_l in lines[:idx]):
                return "", normalized, False
            start_idx = idx
            break

    if start_idx is None:
        # No recognized email header block found
        return "", normalized, False

    header_lines: List[str] = []
    consecutive_empty = 0
    end_idx = len(lines)
    header_count = 0

    for idx in range(start_idx, len(lines)):
        line = lines[idx]
        stripped = line.strip()

        if not stripped:
            consecutive_empty += 1
            if header_count >= 1 and consecutive_empty >= 1:
                # Lookahead to see if next non-empty line continues headers or starts body
                next_non_empty = None
                for future in lines[idx + 1: idx + 4]:
                    if future.strip():
                        next_non_empty = future.strip()
                        break
                if next_non_empty and not match_header_key(next_non_empty):
                    end_idx = idx
                    break
            continue
        else:
            consecutive_empty = 0

        # Check if line starts a new header key
        header_match = match_header_key(line)
        if header_match:
            header_count += 1
            header_lines.append(line)
            continue

        # Check for body boundary or forwarded divider
        if is_body_boundary(line) or is_forward_divider(line):
            end_idx = idx
            break

        # Check for multiline continuation (line starts with whitespace or continuation token)
        is_indented = line.startswith(" ") or line.startswith("\t")
        has_recipient_tokens = bool(EMAIL_REGEX.search(line) or ";" in line or "<" in line)

        if header_count > 0 and (is_indented or has_recipient_tokens):
            # Header line continuation
            header_lines.append(line)
        else:
            # Reached body text
            end_idx = idx
            break

    header_block = "\n".join(header_lines).strip()
    body_content = "\n".join(lines[end_idx:]).strip()

    return header_block, body_content, bool(header_block and header_count > 0)


def unfold_headers(header_block: str) -> Dict[str, str]:
    """Unfold multiline headers into a dictionary of { canonical_key: full_unfolded_value }."""
    if not header_block:
        return {}

    unfolded: Dict[str, List[str]] = {}
    current_key: Optional[str] = None

    for line in header_block.split("\n"):
        match = match_header_key(line)
        if match:
            key, val = match
            current_key = key
            if current_key not in unfolded:
                unfolded[current_key] = []
            if val:
                unfolded[current_key].append(val)
        elif current_key is not None:
            # Continuation line
            val = line.strip()
            if val:
                unfolded[current_key].append(val)

    # Join unfolded lines with space or delimiter
    result: Dict[str, str] = {}
    for k, parts in unfolded.items():
        if k in ("to", "cc", "bcc"):
            # Semicolon/comma preserved
            result[k] = " ".join(parts).strip()
        else:
            result[k] = " ".join(parts).strip()

    return result


def extract_subject_and_name(raw_text: str, email: str) -> Tuple[str, str]:
    """Separate subject and sender display name from text preceding the first email in unlabelled formats."""
    if "\n" in raw_text:
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        if len(lines) >= 2:
            subject = "\n".join(lines[:-1]).strip()
            name = lines[-1].strip()
            if not any(sep in name for sep in (" - ", " | ", " -- ")):
                return subject, clean_display_name(name, email)
            raw_text = name

    cleaned = raw_text.rstrip("<([ \t\r\n").strip()
    if not cleaned:
        return "", ""

    local_part = email.split("@")[0].lower()
    email_tokens = [t.lower() for t in re.split(r"[._\-+0-9]", local_part) if len(t) >= 2]

    words = cleaned.split()
    if not words:
        return "", ""

    # Strategy A: Match backwards against email tokens (e.g. Kallol Chakraborty for Kallol.Chakraborty@ltts.com)
    matched_indices = []
    for idx in range(len(words) - 1, max(-1, len(words) - 5), -1):
        w_clean = re.sub(r"^[^\w]+|[^\w]+$", "", words[idx]).lower()
        if not w_clean:
            continue
        if any(tok in w_clean or w_clean in tok for tok in email_tokens) or (
            len(w_clean) == 1 and local_part.startswith(w_clean)
        ):
            matched_indices.append(idx)
        else:
            if matched_indices and (idx == min(matched_indices) - 1):
                subject_markers = {
                    "requirement", "developer", "engineer", "lead", "manager", "architect",
                    "bangalore", "bengaluru", "hyderabad", "pune", "mumbai", "chennai", "noida",
                    "urgent", "opening", "position", "role", "tpc", "plm", "jd", "job"
                }
                if words[idx].isalpha() and words[idx].lower() not in subject_markers and words[idx] not in ("-", "|", "–"):
                    matched_indices.append(idx)
                    continue
            break

    if matched_indices:
        split_point = min(matched_indices)
        if split_point > 0:
            subject = " ".join(words[:split_point]).strip(" -–|:;,")
            name = " ".join(words[split_point:]).strip()
            return subject, clean_display_name(name, email)

    # Strategy B: Common delimiters in subject (e.g. "Subject Title - City Firstname Lastname")
    sep_match = list(re.finditer(r"\s+[-–|]\s+", cleaned))
    if sep_match:
        last_sep = sep_match[-1]
        after_sep = cleaned[last_sep.end():].strip()
        after_words = after_sep.split()

        subject_markers = {
            "bangalore", "bengaluru", "hyderabad", "pune", "mumbai", "chennai", "noida",
            "remote", "hybrid", "onsite", "delhi", "gurgaon", "kolkata"
        }
        if len(after_words) >= 3 and after_words[0].lower() in subject_markers:
            subject = cleaned[:last_sep.end()] + " " + after_words[0]
            name = " ".join(after_words[1:])
            return subject.strip(" -–|:;,"), clean_display_name(name, email)

    # Strategy C: Standard fallback: last 2 words if alphabetic
    if len(words) >= 3 and words[-1].isalpha() and words[-2].isalpha():
        return " ".join(words[:-2]).strip(" -–|:;,"), clean_display_name(" ".join(words[-2:]), email)

    return "", clean_display_name(cleaned, email)


def parse_unlabelled_outlook_headers(raw_text: str) -> Optional[ExtractedEmailHeaders]:
    """Parse unlabelled Outlook copied email headers (e.g. subject, sender, To, CC on consecutive lines or single block)."""
    if not raw_text or not raw_text.strip():
        return None

    normalized = normalize_email_text(raw_text)

    # 1. Identify where email body starts
    boundary_pattern = re.compile(
        r"(?:^|\n|[>\]\)]\s*)\s*(dear\s+[^,\n]+[,:\n]|hi\s+[^,\n]+[,:\n]|hello\s+[^,\n]+[,:\n]|greetings\b|good\s+morning\b|good\s+afternoon\b|job\s*title\s*:|position\s*:|overview\s*:|responsibilities\s*:)",
        re.I,
    )

    b_match = boundary_pattern.search(normalized)
    if b_match:
        boundary_idx = b_match.start(1)
        header_text = normalized[:boundary_idx].strip()
        body_text = normalized[boundary_idx:].strip()
    else:
        # Fallback: inspect lines with emails until blank line or explicit section boundary
        lines = normalized.splitlines()
        header_lines = []
        body_lines = []
        in_header = True
        for line in lines:
            if in_header:
                if EMAIL_REGEX.search(line):
                    header_lines.append(line)
                elif not header_lines and len(line.strip()) < 150:
                    header_lines.append(line)  # Subject line
                elif not line.strip() and header_lines:
                    in_header = False
                elif is_body_boundary(line):
                    in_header = False
                    body_lines.append(line)
                else:
                    if header_lines and any(EMAIL_REGEX.search(hl) for hl in header_lines):
                        in_header = False
                        body_lines.append(line)
                    else:
                        header_lines.append(line)
            else:
                body_lines.append(line)
        header_text = "\n".join(header_lines).strip()
        body_text = "\n".join(body_lines).strip()

    # Find emails in header_text
    matches = list(EMAIL_REGEX.finditer(header_text))
    if not matches:
        return None

    # Strict confidence check:
    # First email must appear within reasonable distance from start
    m0 = matches[0]
    if m0.start() > 300:
        return None

    # Text before first email must not contain signature markers
    pre_first = header_text[:m0.start()]
    if re.search(r"\b(?:regards|thanks|sincerely|cheers|best\s+regards)\b", pre_first, re.I):
        return None

    # Contact 0 is From
    email_0 = m0.group(0).strip().lower()
    end_0 = m0.end()
    if end_0 < len(header_text) and header_text[end_0] in ('>', ']', ')'):
        end_0 += 1

    subject_val, from_name = extract_subject_and_name(pre_first, email_0)
    from_contacts = [EmailContact(name=from_name, email=email_0)]

    # Contacts 1..N
    contacts = []
    prev_end = end_0

    for m in matches[1:]:
        raw_before = header_text[prev_end:m.start()]
        end_pos = m.end()
        if end_pos < len(header_text) and header_text[end_pos] in ('>', ']', ')'):
            end_pos += 1

        has_semicolon = ";" in raw_before
        has_comma = "," in raw_before
        has_newline = "\n" in raw_before

        raw_clean_name = re.sub(r"^[;,\s]+", "", raw_before).rstrip("<([ ")
        name = clean_display_name(raw_clean_name, m.group(0))

        contacts.append({
            "contact": EmailContact(name=name, email=m.group(0).strip().lower()),
            "has_semicolon": has_semicolon,
            "has_comma": has_comma,
            "has_newline": has_newline,
        })
        prev_end = end_pos

    to_contacts: List[EmailContact] = []
    cc_contacts: List[EmailContact] = []

    if len(contacts) == 1:
        to_contacts.append(contacts[0]["contact"])
    elif len(contacts) >= 2:
        clusters = []
        current_cluster = [contacts[0]]
        for c in contacts[1:]:
            # In Outlook, recipients within the same field (To or CC) are joined by semicolons.
            # A lack of semicolon (such as a newline or space boundary between recipient fields)
            # signifies the transition from the To field to the CC field.
            if c["has_semicolon"]:
                current_cluster.append(c)
            elif c["has_comma"] and not c["has_newline"]:
                current_cluster.append(c)
            else:
                clusters.append(current_cluster)
                current_cluster = [c]
        clusters.append(current_cluster)

        to_contacts = [c["contact"] for c in clusters[0]]
        for cl in clusters[1:]:
            for c in cl:
                cc_contacts.append(c["contact"])

    return ExtractedEmailHeaders(
        from_contacts=from_contacts,
        to_contacts=to_contacts,
        cc_contacts=cc_contacts,
        subject=subject_val if subject_val else None,
        header_block=header_text,
        body_content=body_text,
        has_headers=True,
    )


def extract_universal_email_headers(raw_text: str) -> ExtractedEmailHeaders:
    """Primary universal extraction function.

    Parses raw pasted email text into structured From, To, CC contacts,
    Subject, Date, and isolated JD body content.
    Prioritizes explicit labeled headers; falls back to unlabelled Outlook formats.
    """
    if not raw_text or not raw_text.strip():
        return ExtractedEmailHeaders()

    # 1. Attempt explicit labeled email header extraction
    header_block, body_content, has_headers = extract_header_and_body_blocks(raw_text)
    if has_headers:
        unfolded = unfold_headers(header_block)

        from_contacts = parse_recipient_list(unfolded.get("from", ""))
        to_contacts = parse_recipient_list(unfolded.get("to", ""))
        cc_contacts = parse_recipient_list(unfolded.get("cc", ""))
        bcc_contacts = parse_recipient_list(unfolded.get("bcc", ""))

        subject_val = unfolded.get("subject")
        date_val = unfolded.get("date")

        if from_contacts or to_contacts:
            return ExtractedEmailHeaders(
                from_contacts=from_contacts,
                to_contacts=to_contacts,
                cc_contacts=cc_contacts,
                bcc_contacts=bcc_contacts,
                subject=subject_val,
                date=date_val,
                header_block=header_block,
                body_content=body_content,
                has_headers=True,
            )

    # 2. Fallback: check for unlabelled Outlook copied email format
    unlabelled_res = parse_unlabelled_outlook_headers(raw_text)
    if unlabelled_res and unlabelled_res.has_headers:
        return unlabelled_res

    return ExtractedEmailHeaders(body_content=normalize_email_text(raw_text), has_headers=False)


def extract_email_headers_data(raw_text: str, include_metadata: bool = False) -> Dict[str, Any]:
    """Public helper returning the exact JSON contract schema requested:

    {
      "from": [{"name": "...", "email": "..."}],
      "to": [{"name": "...", "email": "..."}],
      "cc": [{"name": "...", "email": "..."}]
    }
    """
    extracted = extract_universal_email_headers(raw_text)
    if include_metadata:
        return extracted.to_full_dict()
    return extracted.to_dict()
