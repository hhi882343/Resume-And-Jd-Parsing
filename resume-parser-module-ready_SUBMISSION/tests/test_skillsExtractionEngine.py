"""
1:1 Port of tests/skillsExtractionEngine.test.ts to pytest.
Preserves exact test suites, test logic, edge-cases, and assertions.
"""
import pytest
import inspect
from unittest.mock import MagicMock, AsyncMock
from src.skillsExtractionEngine import (
    extractSkillsWithEngineSync,
    extractSkillsWithEngine,
    detectSkillSection,
    validateSkillsAgainstSection,
    expandCompoundSkillPhrases,
)


def run_coro(coro):
    stack = [coro]
    val = None
    exc = None
    while stack:
        curr = stack[-1]
        try:
            if exc:
                res = curr.throw(exc)
                exc = None
            else:
                res = curr.send(val)
            if inspect.isawaitable(res):
                stack.append(res)
                val = None
            else:
                val = res
        except StopIteration as e:
            stack.pop()
            val = e.value
            exc = None
        except Exception as e:
            stack.pop()
            exc = e
    if exc:
        raise exc
    return val


# ============================================================================
# 1. Simple Lists and Delimiters
# ============================================================================

def test_1_simple_lists_extracts_comma_separated_skills_list():
    resume = """
John Doe
Software Engineer

Skills
Python, Java, TypeScript, Docker, Kubernetes, PostgreSQL, Redis

Experience
Senior Developer at Acme Corp
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Java', 'TypeScript', 'Docker', 'Kubernetes', 'PostgreSQL', 'Redis']
    assert res['skillsRaw'] == 'Python, Java, TypeScript, Docker, Kubernetes, PostgreSQL, Redis'
    assert res['diagnostics']['method'] == 'deterministic'
    assert res['diagnostics']['sectionLayout'] == 'standard'


def test_1_simple_lists_extracts_semicolon_separated_skills_list():
    resume = """
Technical Skills
Python; Go; Rust; React; Node.js

Experience
Developer at Tech Corp
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Go', 'Rust', 'React', 'Node.js']
    assert res['skillsRaw'] == 'Python, Go, Rust, React, Node.js'


def test_1_simple_lists_extracts_standard_bullet_lists():
    resume = """
Core Skills
\u2022 Python
- Docker
* Kubernetes
\u2022 PostgreSQL
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Docker', 'Kubernetes', 'PostgreSQL']


def test_1_simple_lists_extracts_lowercase_o_bullet_lists_without_splitting_words():
    resume = """
Technical Skills
o Python
o Docker
o MongoDB
o Oracle Database
o Node.js
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Docker', 'MongoDB', 'Oracle Database', 'Node.js']


def test_1_simple_lists_handles_slash_delimiter_with_spaces_without_corrupting_ci_cd():
    resume = """
Technical Skills
Python / Django / Docker / CI/CD / PL/SQL
"""
    res = extractSkillsWithEngineSync(resume)
    assert 'Python' in res['skills']
    assert 'Django' in res['skills']
    assert 'Docker' in res['skills']
    assert 'CI/CD' in res['skills']
    assert 'PL/SQL' in res['skills']


# ============================================================================
# 2. Tables (Markdown & ASCII)
# ============================================================================

def test_2_tables_extracts_skills_from_markdown_table():
    resume = """
Jane Smith
Full Stack Developer

| Skills |
| Python, TypeScript, Docker, React |

Experience
Full Stack Engineer at Global Corp
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'TypeScript', 'Docker', 'React']
    assert res['diagnostics']['sectionLayout'] == 'table'


def test_2_tables_extracts_skills_from_ascii_border_table_with_category_column():
    resume = """
+--------------------+------------------------+
| Category           | Skills                 |
+--------------------+------------------------+
| Languages          | Python, Go, TypeScript |
| Cloud              | AWS, Docker            |
+--------------------+------------------------+

Experience
Cloud Engineer at Alpha Inc
"""
    res = extractSkillsWithEngineSync(resume)
    assert 'Python' in res['skills']
    assert 'Go' in res['skills']
    assert 'TypeScript' in res['skills']
    assert 'AWS' in res['skills']
    assert 'Docker' in res['skills']
    assert res['diagnostics']['sectionLayout'] == 'table'


def test_2_tables_stops_table_extraction_at_next_section_boundary():
    resume = """
| Skills | Python, React, Docker |
| Experience | 5 years developing software at Google using Java and C++ |
| Education | BS Computer Science |
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'React', 'Docker']
    assert 'Java' not in res['skills']
    assert 'C++' not in res['skills']


# ============================================================================
# 3. Two-Column Layouts
# ============================================================================

def test_3_two_column_extracts_skills_when_skills_in_left_column():
    resume = """
Skills                          Professional Experience
Python, Docker, AWS             Senior Engineer at TechCo
React, TypeScript               Built scalable backend microservices
PostgreSQL                      Managed engineering teams
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Docker', 'AWS', 'React', 'TypeScript', 'PostgreSQL']
    assert res['diagnostics']['sectionLayout'] == 'two_column'


def test_3_two_column_extracts_skills_when_skills_in_right_column():
    resume = """
Professional Experience\t\tTechnical Skills
Senior Engineer at TechCo\t\tPython, Docker, Kubernetes
Built distributed systems\t\tTerraform, AWS, Go
Education\t\t\t\tProjects
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Docker', 'Kubernetes', 'Terraform', 'AWS', 'Go']
    assert res['diagnostics']['sectionLayout'] == 'two_column'


# ============================================================================
# 4. Unusual Headings and Section Formats
# ============================================================================

@pytest.mark.parametrize("snippet,expected_title", [
    ("=== Technical Expertise ===\nPython, Docker, AWS", "Technical Expertise"),
    ("1. Tools & Technologies:\nPython, Docker, AWS", "Tools & Technologies"),
    ("Core Competencies\nPython, Docker, AWS", "Core Competencies"),
    ("Software Skills\nPython, Docker, AWS", "Software Skills"),
    ("Key Skills\nPython, Docker, AWS", "Key Skills"),
    ("Section 2: Technical Skills\nPython, Docker, AWS", "Technical Skills"),
])
def test_4_unusual_headings_detects_variant(snippet, expected_title):
    full_resume = f"{snippet}\n\nExperience\nEngineer at Beta Corp"
    res = extractSkillsWithEngineSync(full_resume)
    assert res['skills'] == ['Python', 'Docker', 'AWS']
    assert res['diagnostics']['sectionDetected'] is True


def test_4_unusual_headings_handles_single_line_inline_heading():
    resume = """
Jane Doe
Technical Skills: Python, Docker, React, AWS
Work Experience
Software Engineer
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Docker', 'React', 'AWS']
    assert res['diagnostics']['sectionLayout'] == 'inline'


# ============================================================================
# 5. Missing Skills Section – Fallback to Other Sections
# ============================================================================

def test_5_missing_skills_extracts_explicit_skills_from_work_experience():
    resume = """
John Doe
Software Engineer

Professional Summary
Experienced full stack developer with expertise in building scalable applications.

Work Experience
Senior Software Engineer - Acme Corp (2020 - Present)
- Developed REST APIs and microservices using Python and Go.
- Deployed cloud infrastructure on AWS using Docker and Terraform.

Education
B.S. in Computer Science - University of California
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['diagnostics']['sectionDetected'] is False
    assert res['diagnostics']['method'] == 'fallback_sections'
    assert 'REST APIs' in res['skills']
    assert 'Microservices' in res['skills']
    assert 'Python' in res['skills']
    assert 'Go' in res['skills']
    assert 'AWS' in res['skills']
    assert 'Docker' in res['skills']
    assert 'Terraform' in res['skills']
    assert len(res['skills']) <= 10


def test_5_missing_skills_returns_empty_array_when_no_evidenced_skills():
    resume = """
John Doe
Administrative Assistant

Work Experience
Project Coordinator - Beta Corp (2021 - Present)
- Responsible for scheduling team meetings and client syncs
- Managed daily agendas and followed up on deliverables
- Worked on a project for a banking client
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == []
    assert res['skillsRaw'] is None
    assert res['diagnostics']['sectionDetected'] is False


def test_5_missing_skills_returns_empty_array_for_empty_or_whitespace_resume():
    res = extractSkillsWithEngineSync('   \n\n  ')
    assert res['skills'] == []
    assert res['skillsRaw'] is None
    assert res['diagnostics']['sectionDetected'] is False


# ============================================================================
# 6. Primary Source Priority vs Fallback Rules
# ============================================================================

def test_6_primary_source_prioritizes_dedicated_skills_section():
    resume = """
Technical Skills
Python, Java, Docker

Work Experience
Senior Backend Engineer (2018 - Present)
Responsibilities:
- Maintained production Kubernetes clusters and Docker containers.
- Implemented data pipelines using Python, Apache Spark, and PostgreSQL.
- Architected cloud solutions using AWS and Terraform.

Projects
E-commerce Platform: Built using React, Node.js, and MongoDB.
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Java', 'Docker']
    assert res['skillsRaw'] == 'Python, Java, Docker'
    assert 'Kubernetes' not in res['skills']
    assert 'React' not in res['skills']
    assert 'MongoDB' not in res['skills']
    assert res['diagnostics']['sectionDetected'] is True
    assert res['diagnostics']['method'] == 'deterministic'


def test_6_primary_source_rejects_responsibility_sentences_inside_skills_section():
    resume = """
Technical Skills
- Designed and developed automated CI/CD pipelines.
- Responsible for microservice maintenance and database tuning.
- Python
- Docker
- AWS
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Docker', 'AWS']
    assert 'Designed and developed automated CI/CD pipelines.' not in res['skills']
    assert 'Responsible for microservice maintenance and database tuning.' not in res['skills']
    assert res['diagnostics']['validationFailuresCount'] > 0


# ============================================================================
# 7. Wrapped Lines Across Multiple Lines
# ============================================================================

def test_7_wrapped_lines_re_stitches_wrapped_lines_correctly():
    resume = """
Technical Skills
Programming Languages: Python, JavaScript,
TypeScript, Go,
Rust, C++

Experience
Developer at Gamma Corp
"""
    res = extractSkillsWithEngineSync(resume)
    assert 'Python' in res['skills']
    assert 'JavaScript' in res['skills']
    assert 'TypeScript' in res['skills']
    assert 'Go' in res['skills']
    assert 'Rust' in res['skills']
    assert 'C++' in res['skills']


# ============================================================================
# 8. Maximum 10 Unique Skills Cap
# ============================================================================

def test_8_max_10_unique_skills_cap_and_deduplicates():
    resume = """
Technical Skills
Python, Java, Docker, Kubernetes, AWS, PostgreSQL, Redis, React, TypeScript, Go, C++, Rust, GraphQL, Ruby
"""
    res = extractSkillsWithEngineSync(resume)
    assert len(res['skills']) == 10
    assert res['skills'] == [
        'Python', 'Java', 'Docker', 'Kubernetes', 'AWS',
        'PostgreSQL', 'Redis', 'React', 'TypeScript', 'Go'
    ]


# ============================================================================
# 9. Compound Skill Expansion
# ============================================================================

def test_9_compound_skill_expansion_cad_and_engineering():
    expanded = expandCompoundSkillPhrases('Surface, Solid Modeling and Drafting')
    assert 'Surface Modeling' in expanded
    assert 'Solid Modeling' in expanded
    assert 'Drafting' in expanded


def test_9_compound_skill_expansion_frontend_and_backend():
    expanded = expandCompoundSkillPhrases('Frontend & Backend Development')
    assert 'Frontend Development' in expanded
    assert 'Backend Development' in expanded


# ============================================================================
# 10. AI Fallback Behavior
# ============================================================================

def test_10_ai_fallback_invokes_fallback_when_deterministic_finds_0():
    resume = """
Technical Skills
Familiarized with modern containerization methodologies and cloud infrastructure orchestration.

Experience
Engineer at Delta Corp
"""
    mock_ai_fallback = AsyncMock(return_value=['Docker', 'Kubernetes'])

    res = run_coro(extractSkillsWithEngine(resume, {
        'enableAiFallback': True,
        'aiFallbackFn': mock_ai_fallback,
    }))

    mock_ai_fallback.assert_called()
    assert 'Docker' in res['diagnostics']['validationFailures']
    assert res['skills'] == []


def test_10_ai_fallback_validates_tokens_against_source_section_text():
    resume = """
Technical Skills
Core stack consists of Go and Rust programming.

Experience
Engineer at Delta Corp
"""
    mock_ai_fallback = AsyncMock(return_value=['Go', 'Rust', 'Python'])

    res = run_coro(extractSkillsWithEngine(resume, {
        'enableAiFallback': True,
        'aiFallbackFn': mock_ai_fallback,
    }))

    mock_ai_fallback.assert_called()

    assert 'Go' in res['skills']
    assert 'Rust' in res['skills']
    assert 'Python' not in res['skills']


# ============================================================================
# 11. Integration with applyEvidenceLock
# ============================================================================

from src.metaforgeParser import applyEvidenceLock


def test_11_integration_preserves_candidate_name_education_experience():
    resume = """
John Doe
john.doe@example.com
+1-555-123-4567

Summary
Full Stack Engineer with 5 years of experience.

Technical Skills
Python, Docker, AWS, React, PostgreSQL

Experience
Senior Developer at Acme Corp
Jan 2019 - Present (5 years)
"""
    locked = applyEvidenceLock(
        {
            'candidateName': 'John Doe',
            'email': 'john.doe@example.com',
            'contactNumber': '+1-555-123-4567',
            'linkedinUrl': None,
            'highestQualification': 'B.Tech',
            'totalExperience': '5 years',
            'relevantExperience': None,
            'skillsRaw': None,
            'technologiesRaw': None,
            'currentEmployer': 'Acme Corp',
            'sourceFile': 'test.pdf',
            'parser': 'legacy',
        },
        resume,
    )

    assert locked['candidateName'] == 'John Doe'
    assert locked['email'] == 'john.doe@example.com'
    assert locked['totalExperience'] == '5 years'
    assert locked['relevantExperience'] is None
    assert locked['skillsRaw'] == 'Python, Docker, AWS, React, PostgreSQL'



# ============================================================================
# 12. Prompt Specification Examples & Edge Cases
# ============================================================================

def test_12_primary_example_1_comma_separated_list_under_skills():
    resume = """
Alice Smith
alice@example.com

Skills
Python, Docker, Kubernetes, AWS, SQL

Experience
Developer at Alpha Inc
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Docker', 'Kubernetes', 'AWS', 'SQL']
    assert res['skillsRaw'] == 'Python, Docker, Kubernetes, AWS, SQL'


def test_12_primary_example_2_inline_heading():
    resume = """
Bob Data
bob@example.com

Technical Skills: Python, Pandas, NumPy

Experience
Data Analyst at Metrics Inc
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Pandas', 'NumPy']
    assert res['skillsRaw'] == 'Python, Pandas, NumPy'


@pytest.mark.parametrize("heading", [
    'Skills',
    'Technical Skills',
    'Key Skills',
    'Core Competencies',
    'Technical Expertise',
    'Professional Skills',
    'Tools and Technologies',
    'Programming Languages',
    'Software Skills',
])
def test_12_detects_heading_and_extracts_explicit_skills(heading):
    resume = f"""
Candidate Name
cand@example.com

{heading}
Python, React, PostgreSQL

Experience
Software Engineer at Delta Corp
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'React', 'PostgreSQL']
    assert res['diagnostics']['sectionDetected'] is True


def test_12_fallback_example_a_summary():
    resume = """
John Doe
john@example.com

Professional Summary
Experienced in Python programming, machine learning, and data analysis.

Work Experience
Engineer at Alpha Inc
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['diagnostics']['sectionDetected'] is False
    assert res['diagnostics']['method'] == 'fallback_sections'
    assert 'Python' in res['skills']
    assert 'Machine Learning' in res['skills']
    assert 'Data Analysis' in res['skills']


def test_12_fallback_example_b_responsibilities():
    resume = """
Jane Doe
jane@example.com

Work Experience
Backend Developer at Beta LLC
- Developed REST APIs using Python and Flask and integrated PostgreSQL.
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['diagnostics']['sectionDetected'] is False
    assert res['diagnostics']['method'] == 'fallback_sections'
    assert 'Python' in res['skills']
    assert 'Flask' in res['skills']
    assert 'REST APIs' in res['skills']
    assert 'PostgreSQL' in res['skills']


def test_12_fallback_example_c_role_description():
    resume = """
Chris Green
chris@example.com

Work Experience
Customer Operations Associate at Gamma Corp
- Managed customer queries, resolved complaints, and coordinated with internal teams.
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['diagnostics']['sectionDetected'] is False
    assert res['diagnostics']['method'] == 'fallback_sections'
    assert 'Customer Service' in res['skills']
    assert 'Problem Resolution' in res['skills']
    assert 'Team Coordination' in res['skills']


def test_12_fallback_example_d_project():
    resume = """
Dana White
dana@example.com

Projects
- Built a machine learning model using Scikit-learn and XGBoost.
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['diagnostics']['sectionDetected'] is False
    assert res['diagnostics']['method'] == 'fallback_sections'
    assert 'Machine Learning' in res['skills']
    assert 'Scikit-learn' in res['skills']
    assert 'XGBoost' in res['skills']


def test_12_decision_case_1_dedicated_skills_section():
    resume = """
Eve Online
eve@example.com

Core Competencies
Java, Spring Boot, MySQL

Work Experience
Senior Developer
- Implemented microservices using Python, Docker, and Kubernetes.
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Java', 'Spring Boot', 'MySQL']
    assert 'Python' not in res['skills']
    assert 'Docker' not in res['skills']
    assert 'Kubernetes' not in res['skills']


def test_12_decision_case_2_no_dedicated_skills_fallback():
    resume = """
Frank Ocean
frank@example.com

Career Summary
Full stack developer with hands-on experience in React and Node.js.

Work Experience
Engineer at Delta Corp
- Built REST APIs and microservices.
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['diagnostics']['sectionDetected'] is False
    assert 'React' in res['skills']
    assert 'Node.js' in res['skills']
    assert 'REST APIs' in res['skills']
    assert 'Microservices' in res['skills']


def test_12_decision_case_3_empty_skills_section_fallback():
    resume = """
Grace Hopper
grace@example.com

Technical Skills
None / N/A

Summary
Experienced in Python programming and PostgreSQL database design.
"""
    res = extractSkillsWithEngineSync(resume)
    assert 'Python' in res['skills']
    assert 'PostgreSQL' in res['skills']


def test_12_decision_case_4_populated_skills_section_preserves_primary():
    resume = """
Hank Pym
hank@example.com

Technical Skills
Python, Django, PostgreSQL

Work Experience
Lead Developer
- Conducted code reviews for team members.
- Maintained legacy PHP and C++ applications.
- Deployed AWS Lambda functions with Terraform.
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == ['Python', 'Django', 'PostgreSQL']
    assert 'PHP' not in res['skills']
    assert 'C++' not in res['skills']
    assert 'Terraform' not in res['skills']


def test_12_strict_does_not_extract_degrees_titles_companies_dates():
    resume = """
Ivy League
ivy@example.com

Professional Summary
Senior Software Engineer at Google with a B.Tech in Computer Science from 2018 to 2022.
Experience in Python and Docker.
"""
    res = extractSkillsWithEngineSync(resume)
    assert 'Python' in res['skills']
    assert 'Docker' in res['skills']
    assert 'Senior Software Engineer' not in res['skills']
    assert 'Google' not in res['skills']
    assert 'B.Tech' not in res['skills']
    assert 'Computer Science' not in res['skills']
    assert '2018' not in res['skills']
    assert '2022' not in res['skills']


def test_12_strict_returns_max_10_distinct_skills():
    resume = """
Jack Ryan
jack@example.com

Technical Skills
Python, Java, Go, Rust, C++, C, TypeScript, JavaScript, Kotlin, Swift, Ruby, PHP, Scala
"""
    res = extractSkillsWithEngineSync(resume)
    assert len(res['skills']) == 10
    assert len(set(res['skills'])) == 10


def test_12_strict_returns_empty_when_no_reliable_skills():
    resume = """
Kelly Clarkson
kelly@example.com

Summary
Hardworking and passionate professional seeking a challenging role.

Experience
Operations Associate
- Organized team files and responded to correspondence.
- Attended weekly status reviews.
"""
    res = extractSkillsWithEngineSync(resume)
    assert res['skills'] == []
    assert res['skillsRaw'] is None


def test_12_layout_table_column_isolation():
    resume = """
Leo Tolstoy
leo@example.com

| Technical Skills | Professional Experience |
| Python, Docker   | Managed client deployments and resolved tickets |
| React, PostgreSQL| Designed user interfaces and maintained servers |
"""
    res = extractSkillsWithEngineSync(resume)
    assert 'Python' in res['skills']
    assert 'Docker' in res['skills']
    assert 'React' in res['skills']
    assert 'PostgreSQL' in res['skills']
    assert 'Managed client deployments and resolved tickets' not in res['skills']
    assert 'Designed user interfaces and maintained servers' not in res['skills']


def test_12_layout_two_column_layout_left_column():
    resume = """
Candidate Name
cand@test.com

Technical Skills        Work Experience
Python                  Senior Engineer at Corp
Docker                  Built scalable architectures
Kubernetes              Mentored junior teammates
AWS                     Maintained system availability
"""
    res = extractSkillsWithEngineSync(resume)
    assert 'Python' in res['skills']
    assert 'Docker' in res['skills']
    assert 'Kubernetes' in res['skills']
    assert 'AWS' in res['skills']


def test_13_parenthetical_hyphenated_skills_do_not_fragment():
    resume = """
Gandham Punith Kumar
Global Immigration Manager
Secunderabad, India | 8247304336 | punithg89@gmail.com 

CORE COMPETENCIES
• U.S. Immigration (H-1B, L-1, PERM, Green Card)
• UK Immigration & Sponsor Compliance
• Global Mobility Programs
• Work Authorization Management
• Certificate of Sponsorship (CoS)
• Right-to-Work Compliance

PROFESSIONAL ACHIEVEMENTS
13+ years of experience
"""
    res = extractSkillsWithEngineSync(resume)
    assert 'U.S. Immigration' in res['skills']
    assert 'H-1B' in res['skills']
    assert 'L-1' in res['skills']
    assert 'PERM' in res['skills']
    assert 'Green Card' in res['skills']
    assert 'UK Immigration & Sponsor Compliance' in res['skills']
    assert 'Global Mobility Programs' in res['skills']
    assert 'Work Authorization Management' in res['skills']
    for bad in ['U.S. Immigration (H', '1B', 'Green Card)', 'Right-to']:
        assert bad not in res['skills']

