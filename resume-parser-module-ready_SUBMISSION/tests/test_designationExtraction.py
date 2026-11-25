import pytest
from src.parseCoreResumeFields import parseCoreFieldsFromResumeText
from src.jsRegex import compile_re


def test_1_extracts_designation_from_professional_summary():
    resume_text = '\n'.join([
        'John Doe',
        'john.doe@example.com',
        '+91 9876543210',
        '',
        'Professional Summary: Experienced Java Full Stack Developer with expertise in Spring Boot and React.',
        '',
        'Technical Skills',
        'Java, Spring Boot, React, SQL',
        '',
        'Education',
        'B.Tech in Computer Science',
    ])

    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['technologiesRaw'] == 'Java Full Stack Developer'
    assert parsed['technologies'] == 'Java Full Stack Developer'
    assert parsed['role'] == 'Java Full Stack Developer'


def test_2_extracts_designation_from_summary():
    resume_text = '\n'.join([
        'Jane Smith',
        'jane.smith@example.com',
        '+91 9876543211',
        '',
        'Summary: Senior Data Engineer with experience in data platforms.',
        '',
        'Technical Skills',
        'Python, SQL, Spark, Kafka',
        '',
        'Education',
        'M.Tech in Data Science',
    ])

    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['technologiesRaw'] == 'Senior Data Engineer'
    assert parsed['technologies'] == 'Senior Data Engineer'
    assert parsed['role'] == 'Senior Data Engineer'


def test_3_extracts_designation_from_profile():
    resume_text = '\n'.join([
        'Rajesh Kumar',
        'rajesh.kumar@example.com',
        '+91 9876543212',
        '',
        'Profile: SAP EWM Functional Consultant.',
        '',
        'Skills',
        'SAP EWM, SAP MM, S/4 HANA',
        '',
        'Education',
        'B.Com from Acharya Nagarjuna University',
    ])

    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['technologiesRaw'] == 'SAP EWM Functional Consultant'
    assert parsed['technologies'] == 'SAP EWM Functional Consultant'
    assert parsed['role'] == 'SAP EWM Functional Consultant'


def test_4_extracts_designation_from_career_summary():
    resume_text = '\n'.join([
        'Anita Sharma',
        'anita.sharma@example.com',
        '+91 9876543213',
        '',
        'Career Summary: Network Engineer with enterprise networking experience.',
        '',
        'Technical Skills',
        'Cisco, Routing, Switching, Firewalls',
        '',
        'Education',
        'B.Tech in Electronics and Communication',
    ])

    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['technologiesRaw'] == 'Network Engineer'
    assert parsed['technologies'] == 'Network Engineer'
    assert parsed['role'] == 'Network Engineer'


def test_5_extracts_designation_from_resume_headline_near_candidate_name():
    resume_text = '\n'.join([
        'LOKESH A',
        'Network Engineer',
        'lokesh.a@example.com',
        '+91 9876543214',
        '',
        'Technical Skills',
        'Routing, Switching, TCP/IP',
        '',
        'Education',
        'B.E. in Information Technology',
    ])

    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['technologiesRaw'] == 'Network Engineer'
    assert parsed['technologies'] == 'Network Engineer'
    assert parsed['role'] == 'Network Engineer'


def test_6_does_not_extract_from_experience_section_when_absent_from_header_and_summary():
    resume_text = '\n'.join([
        'Vikram Patel',
        'vikram.patel@example.com',
        '+91 9876543215',
        '',
        'Experience',
        'Company XYZ (2020 - Present)',
        'Designation: QA Automation Engineer',
        'Responsibilities: writing Selenium tests',
        '',
        'Technical Skills',
        'Selenium, Java, TestNG',
        '',
        'Education',
        'B.Tech in Computer Science',
    ])

    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['technologiesRaw'] is None
    assert parsed['technologies'] is None
    assert parsed['role'] is None


def test_7_returns_null_when_resume_contains_skills_but_no_explicit_designation():
    resume_text = '\n'.join([
        'Pooja Nair',
        'pooja.nair@example.com',
        '+91 9876543216',
        '',
        'Skills: Python, SQL, Machine Learning, Pandas, NumPy',
        '',
        'Education',
        'B.Sc in Statistics',
    ])

    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['technologiesRaw'] is None
    assert parsed['technologies'] is None
    assert parsed['role'] is None
    assert 'Python' in parsed['skillsRaw']


def test_8_follows_source_priority_and_prefers_professional_summary_over_lower_priority_mention_without_merging():
    resume_text = '\n'.join([
        'Suresh Reddy',
        'suresh.reddy@example.com',
        '+91 9876543217',
        '',
        'Professional Summary',
        'Java Developer with 5 years experience',
        '',
        'Work Experience',
        'Previous Role: Python Developer at ABC Corp',
        '',
        'Technical Skills',
        'Java, Python, SQL',
        '',
        'Education',
        'B.Tech in Information Technology',
    ])

    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['technologiesRaw'] == 'Java Developer'
    assert parsed['technologies'] == 'Java Developer'
    assert parsed['role'] == 'Java Developer'


def test_9_returns_null_when_resume_contains_only_personal_info_education_projects_and_skills():
    resume_text = '\n'.join([
        'Ravi Verma',
        'ravi.verma@example.com',
        '+91 9876543218',
        '',
        'Education',
        'B.Tech in Computer Science',
        '',
        'Projects',
        'E-commerce Portal using React and Node.js',
        '',
        'Technical Skills',
        'JavaScript, React, Node.js, MongoDB',
    ])

    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['technologiesRaw'] is None
    assert parsed['technologies'] is None
    assert parsed['role'] is None


from src.metaforgeParser import applyEvidenceLock


def test_10_fallback_parser_applies_strict_designation_rules_and_never_substitutes_skills():
    raw_text = '\n'.join([
        'Deepak Singh',
        'deepak.singh@example.com',
        '+91 9876543219',
        '',
        'Professional Summary: DevOps Engineer with AWS and Kubernetes experience.',
        '',
        'Technical Skills',
        'AWS, Docker, Kubernetes, Terraform',
    ])
    mock_candidate = {
        'candidateName': 'Deepak Singh',
        'email': 'deepak.singh@example.com',
        'contactNumber': '+91 9876543219',
        'linkedinUrl': None,
        'highestQualification': None,
        'skillsRaw': 'AWS, Docker, Kubernetes, Terraform',
        'technologiesRaw': None,
        'totalExperience': '4 Years',
        'relevantExperience': None,
        'currentEmployer': None,
        'sourceFile': 'deepak.pdf',
        'parser': 'legacy',
        'role': None,
    }
    locked = applyEvidenceLock(mock_candidate, raw_text)
    assert locked['technologiesRaw'] == 'DevOps Engineer'
    assert locked['technologies'] == 'DevOps Engineer'
    assert locked['role'] == 'DevOps Engineer'
    assert locked['skillsRaw'] == 'AWS, Docker, Kubernetes, Terraform'
    assert 'Docker' not in (locked['technologiesRaw'] or '')


def test_11_ensures_strict_candidate_isolation_across_multiple_resumes_without_cross_contamination():
    resume_a_text = '\n'.join([
        'Candidate A',
        'cand.a@example.com',
        '+91 9876543220',
        '',
        'Professional Summary: Java Developer with expertise in Spring.',
        '',
        'Technical Skills',
        'Java, Spring',
    ])
    resume_b_text = '\n'.join([
        'Candidate B',
        'cand.b@example.com',
        '+91 9876543221',
        '',
        'Professional Summary: Network Engineer with CCNA certification.',
        '',
        'Technical Skills',
        'Routing, Switching',
    ])
    parsed_a = parseCoreFieldsFromResumeText(resume_a_text)
    parsed_b = parseCoreFieldsFromResumeText(resume_b_text)
    assert parsed_a['technologiesRaw'] == 'Java Developer'
    assert parsed_a['technologies'] == 'Java Developer'
    assert parsed_b['technologiesRaw'] == 'Network Engineer'
    assert parsed_b['technologies'] == 'Network Engineer'

    locked_a = applyEvidenceLock(
        {
            'candidateName': 'Candidate A',
            'email': 'cand.a@example.com',
            'contactNumber': '+91 9876543220',
            'linkedinUrl': None,
            'highestQualification': None,
            'skillsRaw': 'Java, Spring',
            'technologiesRaw': None,
            'totalExperience': None,
            'relevantExperience': None,
            'currentEmployer': None,
            'sourceFile': 'resumeA.txt',
            'parser': 'legacy',
        },
        resume_a_text,
    )

    locked_b = applyEvidenceLock(
        {
            'candidateName': 'Candidate B',
            'email': 'cand.b@example.com',
            'contactNumber': '+91 9876543221',
            'linkedinUrl': None,
            'highestQualification': None,
            'skillsRaw': 'Routing, Switching',
            'technologiesRaw': None,
            'totalExperience': None,
            'relevantExperience': None,
            'currentEmployer': None,
            'sourceFile': 'resumeB.txt',
            'parser': 'legacy',
        },
        resume_b_text,
    )

    assert locked_a['technologiesRaw'] == 'Java Developer'
    assert locked_b['technologiesRaw'] == 'Network Engineer'
    assert locked_a['technologiesRaw'] != locked_b['technologiesRaw']


def test_12_preserves_candidatename_email_phone_education_experience_and_skills_completely_unchanged():
    resume_text = '\n'.join([
        'Sunita Rao',
        'sunita.rao@gmail.com',
        '+91 9876543222',
        'https://www.linkedin.com/in/sunitarao',
        '',
        'Professional Summary: Senior Python Developer with 6 years of experience.',
        '',
        'Total Experience: 6 years',
        '',
        'Technical Skills',
        'Python, Django, FastAPI, PostgreSQL',
        '',
        'Education',
        'B.Tech in Computer Science',
        '',
        'Experience',
        'Tech Corp (2018 - Present)',
        'Senior Python Developer',
    ])

    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['candidateName'] == 'Sunita Rao'
    assert parsed['email'] == 'sunita.rao@gmail.com'
    assert parsed['contactNumber'] == '+919876543222'
    assert parsed['linkedinUrl'] == 'https://www.linkedin.com/in/sunitarao'
    assert compile_re(r'B\.?\s*Tech', 'i').search(parsed['highestQualification'])
    assert compile_re(r'6\s*years', 'i').search(parsed['totalExperienceText'])
    assert 'Python' in parsed['skillsRaw']
    assert 'Django' in parsed['skillsRaw']
    assert parsed['technologiesRaw'] == 'Senior Python Developer'




def test_13_header_overrides_summary_kommu_abhishek():
    resume_text = '\n'.join([
        'KOMMU ABHISHEK',
        'Quality Inspector – In-Process & Final Inspection | Aerospace Manufacturing',
        'abhishek.kommu@example.com',
        '+91 9876543230',
        '',
        'PROFESSIONAL SUMMARY',
        'Mechanical Engineer with 2 years of aerospace in-process and final inspection experience at GE Aerospace.',
        '',
        'TECHNICAL SKILLS',
        'Inspection, CMM, Vernier Caliper, GD&T',
        '',
        'EDUCATION',
        'B.Tech in Mechanical Engineering',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Quality Inspector'
    assert parsed['technologiesRaw'] == 'Quality Inspector'
    assert 'Mechanical' not in (parsed['role'] or '')


def test_14_header_missing_falls_back_to_summary():
    resume_text = '\n'.join([
        'Aakash Verma',
        'aakash.v@example.com',
        '+91 9876543231',
        '',
        'PROFESSIONAL SUMMARY',
        'Results-driven Python Developer with 4 years of experience building scalable backend APIs.',
        '',
        'TECHNICAL SKILLS',
        'Python, FastAPI, Django, PostgreSQL',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Python Developer'


def test_15_summary_explicit_designation():
    resume_text = '\n'.join([
        'Sneha Roy',
        'sneha@example.com',
        '',
        'Professional Summary: Senior Data Engineer with experience in data platforms.',
        '',
        'Skills: Spark, Hadoop, SQL',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Senior Data Engineer'


def test_16_header_title_takes_priority_over_differing_experience_title():
    resume_text = '\n'.join([
        'Kunal Sen',
        'Lead Cloud Architect',
        'kunal.sen@example.com',
        '+91 9876543232',
        '',
        'PROFESSIONAL SUMMARY',
        'Computer Science graduate with 5 years of software development experience in cloud environments.',
        '',
        'WORK EXPERIENCE',
        'Acme Technologies (2019 - Present)',
        'Senior Software Engineer',
        'Responsibilities: Building distributed services',
        '',
        'TECHNICAL SKILLS',
        'Go, Kubernetes, Docker',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Lead Cloud Architect'
    assert parsed['role'] != 'Senior Software Engineer'


def test_17_header_designation_and_domain_separated_by_pipe():
    resume_text = '\n'.join([
        'MANU C R',
        'Quality Engineer | Aerospace Specialist',
        'manu.cr@example.com',
        '',
        'Technical Skills',
        'Quality Assurance, Inspection, ISO 9001',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Quality Engineer'


def test_18_header_designation_and_specialization_separated_by_dash():
    resume_text = '\n'.join([
        'Aditya Mehta',
        'Full Stack Developer – MERN Stack',
        'aditya.m@example.com',
        '',
        'Skills',
        'MongoDB, Express, React, Node.js',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Full Stack Developer'


def test_19_resume_has_no_summary_extracts_from_header():
    resume_text = '\n'.join([
        'MANU C R',
        'Quality Engineer',
        'manu.cr@example.com',
        '+91 9876543233',
        '',
        'Technical Skills',
        'Six Sigma, Quality Control, Auditing',
        '',
        'Education',
        'B.E. in Mechanical Engineering',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Quality Engineer'


def test_20_multi_column_header_layout():
    resume_text = '\n'.join([
        'PRIYA',
        'priya@example.com',
        '+91 9876543234',
        'Data Analyst',
        'Bangalore, India',
        '',
        'Skills',
        'SQL, Power BI, Python, Excel',
        '',
        'Education',
        'B.Sc in Computer Science',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Data Analyst'


def test_21_header_contains_multiple_job_titles_prefers_first_primary():
    resume_text = '\n'.join([
        'RAHUL KUMAR',
        'Senior Java Developer | Backend Engineer',
        'rahul.k@example.com',
        '+91 9876543235',
        '',
        'Skills',
        'Java, Spring Boot, Microservices',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Senior Java Developer'


def test_22_no_identifiable_designation_returns_none():
    resume_text = '\n'.join([
        'Ananya Gupta',
        'ananya.g@example.com',
        '+91 9876543236',
        '',
        'Education',
        'Bachelor of Technology in Computer Science',
        '',
        'Personal Projects',
        'Weather App built with React and OpenWeatherMap API',
        '',
        'Technical Skills',
        'Python, HTML, CSS, JavaScript, Git',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] is None


def test_23_additional_separator_examples():
    cases = [
        ('Mechanical Design Engineer | CAD Specialist', 'Mechanical Design Engineer'),
        ('Data Analyst – SQL & Power BI', 'Data Analyst'),
        ('Lead Python Developer', 'Lead Python Developer'),
    ]
    for headline, expected in cases:
        text = f"Candidate Name\n{headline}\nemail@test.com\n\nSkills\nSkill1, Skill2\n"
        res = parseCoreFieldsFromResumeText(text)
        assert res['role'] == expected, f"Failed on headline '{headline}', got '{res['role']}'"


def test_24_naukri_format_rejects_section_headings_as_role_and_skills():
    resume_text = '\n'.join([
        'Chandrakala K S',
        'nishaprashanth4831@gmail.com | +91 70190 40105 | Bengaluru, Karnataka',
        '',
        'Resume Headline:',
        'Quality Engineer with 4.5 Years of Experience in Aerospace Manufacturing & Mechanical Inspection',
        '',
        'PROFESSIONAL SUMMARY',
        'Experienced Quality Engineer with 4.5 years of experience in quality control, CMM inspection, and GD&T.',
        '',
        'Key Skills:',
        'Quality Control, GD&T, CMM Inspection, AutoCAD, SolidWorks, Calipers, Micrometers',
        '',
        'Work Experience:',
        'Current Organization: Bharat Forge Aerospace Ltd',
        'Designation: Quality Engineer',
        'Duration: Dec 2021 – Present (3.5 years)',
        '',
        'Education:',
        'Diploma mechanical engineer',
        '',
        'ACHIEVEMENTS:',
        'Best Employee Award',
        '',
        'AWARDS:',
        'Quality Excellence Award',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Quality Engineer'
    assert parsed['role'] != 'PROFESSIONAL SUMMARY'
    assert parsed['highestQualification'] == 'Diploma in Mechanical Engineering'
    assert parsed['currentCompany'] == 'Bharat Forge Aerospace Ltd'
    assert 'Quality Control' in (parsed['skillsRaw'] or '')
    assert 'GD&T' in (parsed['skillsRaw'] or '')
    assert 'ACHIEVEMENTS' not in (parsed['skillsRaw'] or '')
    assert 'AWARDS' not in (parsed['skillsRaw'] or '')


def test_25_contextual_role_from_professional_summary():
    resume_text = '\n'.join([
        'Amit Sharma',
        'amit.sharma@example.com',
        '+91 9876543299',
        '',
        'Professional Summary',
        'Experienced professional with 5 years of experience in Java application development and Spring Boot.',
        '',
        'Technical Skills',
        'Java, Spring Boot, Microservices, SQL',
        '',
        'Education',
        'B.Tech in Computer Science',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Java Developer'


def test_26_header_overrides_summary_degree():
    resume_text = '\n'.join([
        'KOMMU ABHISHEK',
        'Quality Inspector – In-Process & Final Inspection | Aerospace Manufacturing',
        'abhishek.k@example.com',
        '+91 9876543298',
        '',
        'Professional Summary',
        'Mechanical Engineer with 4 years of experience in manufacturing and assembly inspection.',
        '',
        'Education',
        'B.E. in Mechanical Engineering',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Quality Inspector'
    assert parsed['role'] != 'Mechanical Engineer'


def test_27_preserve_seniority_levels_in_contextual_role():
    resume_text = '\n'.join([
        'Sneha Roy',
        'sneha.roy@example.com',
        '+91 9876543297',
        '',
        'About Me',
        'Senior professional with 8 years of experience in Python web development and REST APIs.',
        '',
        'Education',
        'B.Sc in Information Technology',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Senior Python Developer'


def test_28_gowrisankar_equipment_and_domain_headline_to_role():
    resume_text = '\n'.join([
        'GOWRISANKAR D',
        'QUALITY ENGINEERING | QUALITY INSPECTION | FIRST ARTICLE INSPECTION',
        'Annangal, Chengalpattu, Tamil Nadu – 603307  |  +91-9087962611  |  gowrisankargowtham@gmail.com',
        'PROFESSIONAL SUMMARY',
        'Quality Engineering and Quality Inspection professional with 8+ years of experience across automotive and aerospace manufacturing environments. Experience includes First Article Inspection (FAI), AS9102, AS9100 Rev. D, Net-Inspect, quality documentation, inspection planning, root-cause analysis, corrective actions, CMM operation, MSA and process audits.',
        'PROFESSIONAL EXPERIENCE',
        'TVS UPASANA PVT LTD, HOSUR',
        'Graduate Trainee  |  Jan 2018 – Jan 2021  |  Quality Assurance',
        'EQUIPMENT HANDLED',
        '• CMM (Zeiss Contura G2), Calypso 2019 and Gear Pro (Zeiss Gear Tester)',
        '• Surface Roughness Tester – Mitutoyo, Mahr',
        '• Roundness Tester – Taylor Hobson, Jenoptik',
        '• Gear Roll Tester – Kudale, Gear Spect',
        'TECHNICAL SKILLS',
        '• AS9102 First Article Inspection (FAI) and AS9100 Rev. D',
        'EDUCATION',
        '• B.E. – Mechanical Engineering, St. Peter\'s College of Engineering (2013–2017)',
    ])
    parsed = parseCoreFieldsFromResumeText(resume_text)
    assert parsed['role'] == 'Quality Engineer'
    assert parsed['role'] != 'Surface Roughness Tester'
    assert parsed['role'] != 'Roundness Tester'



