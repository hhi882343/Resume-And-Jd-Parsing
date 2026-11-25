"""Unit tests for the Universal Email Header Extraction Engine (app/core/email_extractor.py).

Covers:
1. Exact expected JSON schema parity {"from": [...], "to": [...], "cc": [...]}.
2. Gmail copied email format (commas, Date header, Subject in middle).
3. Outlook Desktop/Web copied email format (semicolons, Last, First names, 'Sent:' header, quotes).
4. Multiline wrapped headers (RFC 2822 continuation).
5. Outlook mailto links: Name [mailto:email@domain.com].
6. Bare emails and parenthesized emails: Name (email@domain.com).
7. Missing fields independence: Missing CC -> cc is empty list [], never assigned From email.
8. Body and signature email isolation: Emails inside JD description or footer never pollute headers.
9. Header order invariance: Subject or Date first.
10. Forwarded email divider handling.
11. Angle brackets without space: Name<email@domain.com>.
12. Unicode whitespace, quotes, and newline normalization.
"""

from __future__ import annotations

from app.core.email_extractor import (
    extract_email_headers_data,
    extract_universal_email_headers,
)

# =========================================================================
# 1. Exact Expected Schema & Clean Extraction
# =========================================================================


def test_standard_rfc_header_extraction_exact_schema():
    raw_email = """From: John Smith <john@company.com>
To: Recruitment Team <hr@company.com>
Cc: Hiring Manager <manager@company.com>
Subject: Senior Backend Engineer

Hi Team,
Here is the job requirement for the new position.
"""
    result = extract_email_headers_data(raw_email)

    expected = {
        "from": [{"name": "John Smith", "email": "john@company.com"}],
        "to": [{"name": "Recruitment Team", "email": "hr@company.com"}],
        "cc": [{"name": "Hiring Manager", "email": "manager@company.com"}],
    }

    assert result == expected


# =========================================================================
# 2. Gmail Copied Format (Commas, Date:, Subject in middle, Quotes)
# =========================================================================


def test_gmail_copied_email_format():
    gmail_text = """From: "John Smith" <john@company.com>
Date: Mon, Nov 9, 2026 at 10:15 AM
Subject: Urgent: React Native Lead Developer
To: Recruitment Team <hr@company.com>, "Jane Doe" <jane@company.com>
Cc: Hiring Manager <manager@company.com>, "Lead Architect" <lead@company.com>

Role Overview:
Looking for a React Native specialist with 8+ years experience.
"""
    headers = extract_universal_email_headers(gmail_text)
    data = headers.to_dict()

    assert data["from"] == [{"name": "John Smith", "email": "john@company.com"}]
    assert len(data["to"]) == 2
    assert data["to"][0] == {"name": "Recruitment Team", "email": "hr@company.com"}
    assert data["to"][1] == {"name": "Jane Doe", "email": "jane@company.com"}

    assert len(data["cc"]) == 2
    assert data["cc"][0] == {"name": "Hiring Manager", "email": "manager@company.com"}
    assert data["cc"][1] == {"name": "Lead Architect", "email": "lead@company.com"}

    assert headers.subject == "Urgent: React Native Lead Developer"
    assert "Mon, Nov 9, 2026" in headers.date


# =========================================================================
# 3. Outlook Copied Format (Semicolons, Last, First names, 'Sent:', single quotes)
# =========================================================================


def test_outlook_copied_email_format_with_semicolons_and_last_first():
    outlook_text = """From: Smith, John <john@company.com>
Sent: Monday, November 9, 2026 10:00 AM
To: 'Recruitment Team' <hr@company.com>; Doe, Jane <jane@company.com>
Cc: Manager, Hiring <manager@company.com>
Subject: Cloud Infrastructure Lead

Dear Team,
We urgently need a Cloud Architect for AWS migration.
"""
    result = extract_email_headers_data(outlook_text)

    # In Outlook, "Smith, John" -> display name "John Smith"
    assert result["from"] == [{"name": "John Smith", "email": "john@company.com"}]
    assert result["to"] == [
        {"name": "Recruitment Team", "email": "hr@company.com"},
        {"name": "Jane Doe", "email": "jane@company.com"},
    ]
    assert result["cc"] == [{"name": "Hiring Manager", "email": "manager@company.com"}]


# =========================================================================
# 4. Multiline Wrapped Headers (RFC 2822 / 5322 Folding)
# =========================================================================


def test_multiline_recipient_headers():
    multiline_text = """From: John Smith <john@company.com>
To: Alice Walker <alice@company.com>,
    Bob Vance <bob@company.com>,
    Charlie Day <charlie@company.com>
Cc: Dennis Reynolds <dennis@company.com>,
    Mac McDonald <mac@company.com>
Subject: Full Stack Developer

Job Description:
- 5+ years experience with Python and TypeScript.
"""
    result = extract_email_headers_data(multiline_text)

    assert result["from"] == [{"name": "John Smith", "email": "john@company.com"}]
    assert len(result["to"]) == 3
    assert result["to"][0] == {"name": "Alice Walker", "email": "alice@company.com"}
    assert result["to"][1] == {"name": "Bob Vance", "email": "bob@company.com"}
    assert result["to"][2] == {"name": "Charlie Day", "email": "charlie@company.com"}

    assert len(result["cc"]) == 2
    assert result["cc"][0] == {"name": "Dennis Reynolds", "email": "dennis@company.com"}
    assert result["cc"][1] == {"name": "Mac McDonald", "email": "mac@company.com"}


# =========================================================================
# 5. Outlook Mailto Links Format
# =========================================================================


def test_outlook_mailto_format():
    mailto_text = """From: John Smith [mailto:john@company.com]
Sent: Friday, October 30, 2026 2:15 PM
To: Recruitment Team [mailto:hr@company.com]
Cc: Hiring Manager [mailto:manager@company.com]
Subject: Python Tech Lead - Pune

Hi Team,
Please review the attached profile requirements.
"""
    result = extract_email_headers_data(mailto_text)

    assert result["from"] == [{"name": "John Smith", "email": "john@company.com"}]
    assert result["to"] == [{"name": "Recruitment Team", "email": "hr@company.com"}]
    assert result["cc"] == [{"name": "Hiring Manager", "email": "manager@company.com"}]


# =========================================================================
# 6. Bare Email Addresses & Missing Display Names
# =========================================================================


def test_bare_emails_and_mixed_display_names():
    raw_text = """From: john@company.com
To: <hr@company.com>, Jane Doe <jane@company.com>
Cc: manager@company.com
Subject: Data Engineer Opening

Requirement:
Snowflake, dbt, Python.
"""
    result = extract_email_headers_data(raw_text)

    assert result["from"] == [{"name": "", "email": "john@company.com"}]
    assert len(result["to"]) == 2
    assert result["to"][0] == {"name": "", "email": "hr@company.com"}
    assert result["to"][1] == {"name": "Jane Doe", "email": "jane@company.com"}
    assert result["cc"] == [{"name": "", "email": "manager@company.com"}]


# =========================================================================
# 7. Angle Brackets Without Spaces (User Real-World Case)
# =========================================================================


def test_angle_brackets_without_spaces():
    raw_text = """From: Kallol Chakraborty<Kallol.Chakraborty@Ltts.com>
To: Vinaya Kumar P Patil <Vinayakumarp.Patil_ext@ltts.com>
Subject: TPC - Requirement - Power Electronics Design for Pune

Position: Hardware Engineer
Experience: 5-8 years
"""
    result = extract_email_headers_data(raw_text)

    assert result["from"] == [{"name": "Kallol Chakraborty", "email": "kallol.chakraborty@ltts.com"}]
    assert result["to"] == [{"name": "Vinaya Kumar P Patil", "email": "vinayakumarp.patil_ext@ltts.com"}]
    assert result["cc"] == []


# =========================================================================
# 8. Missing Fields Handled Independently (No Cross-Contamination)
# =========================================================================


def test_missing_cc_field_returns_empty_list_never_from_email():
    """Verify bug fix: CC must never be assigned from From address when CC is absent."""
    raw_text = """From: John Smith <john@company.com>
To: Recruitment Team <hr@company.com>
Subject: SAP SD Consultant

Job Description details...
"""
    result = extract_email_headers_data(raw_text)

    assert result["from"] == [{"name": "John Smith", "email": "john@company.com"}]
    assert result["to"] == [{"name": "Recruitment Team", "email": "hr@company.com"}]
    assert result["cc"] == []  # MUST BE EMPTY, NOT john@company.com!


def test_missing_from_or_to_fields_handled_independently():
    only_to_text = """To: Talent Acquisition <ta@company.com>
Subject: Java Lead Opening

JD details...
"""
    result = extract_email_headers_data(only_to_text)
    assert result["from"] == []
    assert result["to"] == [{"name": "Talent Acquisition", "email": "ta@company.com"}]
    assert result["cc"] == []


# =========================================================================
# 9. Boundary Detection: Emails in Body, Footers, and Signatures Isolated
# =========================================================================


def test_body_and_signature_emails_not_assigned_to_headers():
    complex_email = """From: John Smith <john@company.com>
To: Recruitment Team <hr@company.com>
Subject: Cloud Architect Opening

Hi Team,

Please find the JD below:
Role: Cloud Architect
Location: Remote

Interview details:
- Technical round taken by lead architect at lead.tech@external-vendor.com
- Please send all candidate CVs to cv-dropzone@staffing-partner.com
- Escalations should be sent to executive-sponsor@client.com

Regards,
John Smith
Senior Recruiting Partner
contact-me@personal-domain.net
Disclaimers: Report phishing to security-abuse@company.com
"""
    result = extract_email_headers_data(complex_email)

    assert result["from"] == [{"name": "John Smith", "email": "john@company.com"}]
    assert result["to"] == [{"name": "Recruitment Team", "email": "hr@company.com"}]
    assert result["cc"] == []

    # Verify that NONE of the body emails leaked into headers
    all_emails = [
        c["email"]
        for c_list in (result["from"] + result["to"] + result["cc"])
        for c in [c_list]
    ]
    assert "lead.tech@external-vendor.com" not in all_emails
    assert "cv-dropzone@staffing-partner.com" not in all_emails
    assert "executive-sponsor@client.com" not in all_emails
    assert "contact-me@personal-domain.net" not in all_emails
    assert "security-abuse@company.com" not in all_emails


# =========================================================================
# 10. Arbitrary Header Ordering (Subject First, Date First)
# =========================================================================


def test_arbitrary_header_ordering():
    subject_first_text = """Subject: Urgent Requirement: Principal Architect
From: John Smith <john@company.com>
Date: 09 Nov 2026 14:00
To: Recruitment Team <hr@company.com>
Cc: Hiring Manager <manager@company.com>

Overview of position...
"""
    result = extract_email_headers_data(subject_first_text)

    assert result["from"] == [{"name": "John Smith", "email": "john@company.com"}]
    assert result["to"] == [{"name": "Recruitment Team", "email": "hr@company.com"}]
    assert result["cc"] == [{"name": "Hiring Manager", "email": "manager@company.com"}]


# =========================================================================
# 11. Forwarded Email Divider Handling
# =========================================================================


def test_forwarded_email_boundary_detection():
    forwarded_text = """From: Internal Recruiter <internal@company.com>
Sent: Tuesday, November 10, 2026 9:00 AM
To: Vendor Pool <vendors@agency.com>
Subject: FW: Requirement: Senior SRE

-----Original Message-----
From: Client Manager <manager@client.com>
Sent: Monday, November 9, 2026 18:00
To: Internal Recruiter <internal@company.com>
Subject: Requirement: Senior SRE

Hi,
We need an SRE engineer immediately.
"""
    headers = extract_universal_email_headers(forwarded_text)
    data = headers.to_dict()

    # The top-level email header block is captured
    assert data["from"] == [{"name": "Internal Recruiter", "email": "internal@company.com"}]
    assert data["to"] == [{"name": "Vendor Pool", "email": "vendors@agency.com"}]
    assert data["cc"] == []

    # The body content retains the forwarded message
    assert "Original Message" in headers.body_content
    assert "manager@client.com" not in [c["email"] for c in data["from"]]


# =========================================================================
# 12. Unicode Normalization (CRLF, Non-Breaking Spaces, Smart Quotes)
# =========================================================================


def test_unicode_normalization_crlf_and_smart_quotes():
    nasty_text = (
        "From:\u00a0“Smith,\u00a0John”\u00a0<john@company.com>\r\n"
        "To:\u00a0‘Recruitment\u00a0Team’\u00a0<hr@company.com>\r\n"
        "Cc:\u00a0“Hiring\u00a0Manager”\u00a0<manager@company.com>\r\n"
        "Subject:\u00a0Technical\u00a0Lead\r\n\r\n"
        "Body content here."
    )
    result = extract_email_headers_data(nasty_text)

    assert result["from"] == [{"name": "John Smith", "email": "john@company.com"}]
    assert result["to"] == [{"name": "Recruitment Team", "email": "hr@company.com"}]
    assert result["cc"] == [{"name": "Hiring Manager", "email": "manager@company.com"}]


# =========================================================================
# 13. Unlabelled Outlook Copied Email (Single Line Prompt Example)
# =========================================================================


def test_unlabelled_outlook_copied_single_line_prompt_example():
    text = (
        "TPC - Requirement - PLM - Technical Publication - Bangalore Kallol Chakraborty<Kallol.Chakraborty@Ltts.com> "
        "Arundhati Shivashankarappa Rudagi <Arundhati.Rudagi_ext@Ltts.com>;"
        "Pranati Paul <Pranati.Paul_ext@Ltts.com>;"
        "K V Sai Siri <Kv.Saisiri_ext@Ltts.com> "
        "Ashwini Kudi C E <Ashwini.Kudi@Ltts.com> Dear Partner,"
    )
    headers = extract_universal_email_headers(text)

    # Subject extraction
    assert headers.subject == "TPC - Requirement - PLM - Technical Publication - Bangalore"

    # From extraction
    assert len(headers.from_contacts) == 1
    assert headers.from_contacts[0].name == "Kallol Chakraborty"
    assert headers.from_contacts[0].email == "kallol.chakraborty@ltts.com"

    # To extraction (multiple recipients separated by semicolons)
    assert len(headers.to_contacts) == 3
    assert headers.to_contacts[0].name == "Arundhati Shivashankarappa Rudagi"
    assert headers.to_contacts[0].email == "arundhati.rudagi_ext@ltts.com"
    assert headers.to_contacts[1].name == "Pranati Paul"
    assert headers.to_contacts[1].email == "pranati.paul_ext@ltts.com"
    assert headers.to_contacts[2].name == "K V Sai Siri"
    assert headers.to_contacts[2].email == "kv.saisiri_ext@ltts.com"

    # CC extraction (single recipient)
    assert len(headers.cc_contacts) == 1
    assert headers.cc_contacts[0].name == "Ashwini Kudi C E"
    assert headers.cc_contacts[0].email == "ashwini.kudi@ltts.com"

    # Body boundary starts at "Dear Partner,"
    assert headers.body_content.startswith("Dear Partner,")
    assert headers.has_headers is True


# =========================================================================
# 14. Unlabelled Outlook Copied Email (Multiline Format)
# =========================================================================


def test_unlabelled_outlook_copied_multiline_format():
    text = """TPC - Requirement - PLM - Technical Publication - Bangalore
Kallol Chakraborty<Kallol.Chakraborty@Ltts.com>
Arundhati Shivashankarappa Rudagi <Arundhati.Rudagi_ext@Ltts.com>;Pranati Paul <Pranati.Paul_ext@Ltts.com>;K V Sai Siri <Kv.Saisiri_ext@Ltts.com>
Ashwini Kudi C E <Ashwini.Kudi@Ltts.com>
Dear Partner,
Please find below the JD for the open position."""
    headers = extract_universal_email_headers(text)

    assert headers.subject == "TPC - Requirement - PLM - Technical Publication - Bangalore"
    assert headers.from_contacts[0].name == "Kallol Chakraborty"
    assert headers.from_contacts[0].email == "kallol.chakraborty@ltts.com"

    assert len(headers.to_contacts) == 3
    assert headers.to_contacts[0].name == "Arundhati Shivashankarappa Rudagi"
    assert headers.to_contacts[1].name == "Pranati Paul"
    assert headers.to_contacts[2].name == "K V Sai Siri"

    assert len(headers.cc_contacts) == 1
    assert headers.cc_contacts[0].name == "Ashwini Kudi C E"
    assert headers.cc_contacts[0].email == "ashwini.kudi@ltts.com"

    assert "Please find below the JD" in headers.body_content


# =========================================================================
# 15. Unlabelled Outlook with Missing CC (Independent Missing Handling)
# =========================================================================


def test_unlabelled_outlook_without_cc():
    text = """Senior Staff Engineer - Platform Team
Alice Walker <alice.walker@techcorp.com>
Bob Dylan <bob.dylan@techcorp.com>; Charlie Brown <charlie.b@techcorp.com>
Hi Team,
We need a senior platform engineer."""
    headers = extract_universal_email_headers(text)

    assert headers.subject == "Senior Staff Engineer - Platform Team"
    assert headers.from_contacts[0].name == "Alice Walker"
    assert headers.from_contacts[0].email == "alice.walker@techcorp.com"

    assert len(headers.to_contacts) == 2
    assert headers.to_contacts[0].name == "Bob Dylan"
    assert headers.to_contacts[1].name == "Charlie Brown"

    # CC must remain empty list, not shifted or contaminated
    assert headers.cc_contacts == []


# =========================================================================
# 16. Unlabelled Outlook with Different Company and Comma Separators
# =========================================================================


def test_unlabelled_outlook_comma_separated_recipients():
    text = """Cloud Infrastructure Architect - Hybrid Cloud
Marcus Vance <marcus.vance@acme.org>
Elena Rostova <elena@acme.org>, David Kim <david.kim@acme.org>
Samantha Jones <sjones@acme.org>
Good morning,
Looking for cloud architect resumes."""
    headers = extract_universal_email_headers(text)

    assert "Cloud Infrastructure Architect" in (headers.subject or "")
    assert headers.from_contacts[0].name == "Marcus Vance"
    assert headers.from_contacts[0].email == "marcus.vance@acme.org"

    assert len(headers.to_contacts) == 2
    assert headers.to_contacts[0].name == "Elena Rostova"
    assert headers.to_contacts[1].name == "David Kim"

    assert len(headers.cc_contacts) == 1
    assert headers.cc_contacts[0].name == "Samantha Jones"
    assert headers.cc_contacts[0].email == "sjones@acme.org"


# =========================================================================
# 17. Plain JD Without Headers Does Not Trigger False Positive
# =========================================================================


def test_plain_jd_does_not_falsely_trigger_unlabelled_outlook():
    plain_jd = """Job Title: Senior Data Engineer
Location: Austin, TX
Responsibilities:
- Build ETL pipelines using PySpark and BigQuery
- Maintain Kafka event streams
Apply directly by emailing your resume to careers@dataops.io.
Thanks,
Talent Acquisition Team"""
    headers = extract_universal_email_headers(plain_jd)

    # Must NOT extract careers@dataops.io into from/to/cc
    assert headers.has_headers is False
    assert headers.from_contacts == []
    assert headers.to_contacts == []
    assert headers.cc_contacts == []


# =========================================================================
# 18. Unlabelled Outlook with 1 To and Multiple CC (Never Swapped)
# =========================================================================


def test_unlabelled_outlook_one_to_multiple_cc():
    text = """Staff DevOps Engineer - AWS Cloud
Sender Lead <lead@company.com>
Primary Recipient <primary@company.com>
CC One <cc1@company.com>; CC Two <cc2@company.com>; CC Three <cc3@company.com>
Dear Partner,
JD follows."""
    headers = extract_universal_email_headers(text)

    # To field must have exactly 1 recipient
    assert len(headers.to_contacts) == 1
    assert headers.to_contacts[0].name == "Primary Recipient"
    assert headers.to_contacts[0].email == "primary@company.com"

    # CC field must have 3 recipients
    assert len(headers.cc_contacts) == 3
    assert headers.cc_contacts[0].name == "CC One"
    assert headers.cc_contacts[1].name == "CC Two"
    assert headers.cc_contacts[2].name == "CC Three"


# =========================================================================
# 19. Unlabelled Outlook with 2 To and 2 CC
# =========================================================================


def test_unlabelled_outlook_two_to_two_cc():
    text = """Backend Architect - Core Platform
Tech Director <director@company.com>
To One <to1@company.com>; To Two <to2@company.com>
CC One <cc1@company.com>; CC Two <cc2@company.com>
Hi Team,
Profiles requested."""
    headers = extract_universal_email_headers(text)

    assert len(headers.to_contacts) == 2
    assert headers.to_contacts[0].name == "To One"
    assert headers.to_contacts[1].name == "To Two"

    assert len(headers.cc_contacts) == 2
    assert headers.cc_contacts[0].name == "CC One"
    assert headers.cc_contacts[1].name == "CC Two"


# =========================================================================
# 20. Unlabelled Outlook with 1 To and 1 CC (Separate Lines, No Semicolons)
# =========================================================================


def test_unlabelled_outlook_one_to_one_cc():
    text = """Full Stack Developer
Hiring Manager <manager@company.com>
Lead Recruiter <recruiter@company.com>
Talent Partner <partner@company.com>
Hello All,
We need candidates."""
    headers = extract_universal_email_headers(text)

    assert len(headers.to_contacts) == 1
    assert headers.to_contacts[0].name == "Lead Recruiter"
    assert headers.to_contacts[0].email == "recruiter@company.com"

    assert len(headers.cc_contacts) == 1
    assert headers.cc_contacts[0].name == "Talent Partner"
    assert headers.cc_contacts[0].email == "partner@company.com"


