import pytest
from src.parseCoreResumeFields import (
    parseCoreFieldsFromResumeText,
    extractTotalExperienceInfo,
    extractEligibleSkillsBlock,
    extractWholeResumeSkills,
)
from src.jsRegex import compile_re

def test_1_example_a_nearly_12_years_12_years():
    resume = """A goal-oriented profession with nearly 12 years of experience in Refinery, Petrochemical and Chemical industry."""
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '12 years'
    assert info['years'] == 12

def test_2_example_b_over_7_years_7_years_qualifier_removed_not_added():
    resume = """Over 7 years of experience in mechanical design."""
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '7 years'
    assert info['years'] == 7

def test_3_example_c_7_years_7_years_preserved():
    resume = """7+ years of experience in hardware engineering."""
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '7+ years'
    assert info['years'] == 7

def test_4_example_d_approximately_8_years_8_years():
    resume = """Approximately 8 years of professional experience."""
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '8 years'
    assert info['years'] == 8

def test_5_example_e_4_5_years_4_5_years():
    resume = """4.5+ years of experience in automotive electronics."""
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '4.5+ years'
    assert info['years'] == 4

def test_6_example_f_employment_dates_without_explicit_overall_experien():
    resume = """
    Work Experience
    Company A: 2018 - 2021
    Company B: 2021 - 2026
    """;
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == ''
    assert info['years'] is None

def test_7_months_preserved_without_conversion():
    resume = """36 months of professional experience."""
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '36 months'
    assert info['years'] == 3

def test_8_more_qualifiers_stripped_more_than_having():
    resumeA = """More than 7 years of experience in Cloud Architecture."""
    assert extractTotalExperienceInfo(resumeA)['text'] == '7 years'

    resumeB = """Having 4.10 years of experience."""
    assert extractTotalExperienceInfo(resumeB)['text'] == '4.10 years'

def test_9_extracts_overall_experience_when_relevant_experience_is_also():
    resume = """Having 6 years of overall work experience and relevant experience is 4+ years in embedded systems."""
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '6 years'

def test_10_relevant_experience_only_without_overall_experience_returns_():
    resume = """
    Professional Summary
    Having 4+ years of relevant experience in React and Node.js.
    """;
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == ''
    assert info['years'] is None

def test_11_rule_2_example_cad_skills_breakdown_compound_expansion_fille():
    resume = """
    Skills
    - NX-CAD: Expertise in Surface, Solid Modeling and Drafting.
    - Creo 7.0: Expertise in Surface, Solid Modeling and Drafting.
    - CATIA: Basic Solid Modeling and Drafting.
    - NX Nastran: Component-wise structural CAE Simulation.
    - Microsoft Excel.
    - Microsoft PowerPoint.
    """;
    skills = extractWholeResumeSkills(resume)
    assert skills == [
      'NX-CAD',
      'Surface Modeling',
      'Solid Modeling',
      'Drafting',
      'Creo 7.0',
      'CATIA',
      'NX Nastran',
      'Structural CAE Simulation',
      'Microsoft Excel',
      'Microsoft PowerPoint',
    ]
    assert len(skills) == 10

def test_12_a_skills_section_containing_more_than_10_skills_returns_maxi():
    resume = """
    Technical Skills
    Python, Java, C++, Go, Rust, Ruby, JavaScript, TypeScript, PHP, Swift, Kotlin, Scala
    """;
    skills = extractWholeResumeSkills(resume)
    assert len(skills) == 10
    assert skills == [
      'Python',
      'Java',
      'C++',
      'Go',
      'Rust',
      'Ruby',
      'JavaScript',
      'TypeScript',
      'PHP',
      'Swift',
    ]

def test_13_a_resume_without_a_skills_section_falls_back_to_experience_r():
    resume = """
    Candidate Name
    Professional Experience
    Responsibilities:
    - Managed Kubernetes clusters and Docker containers
    - Developed backend services in Go
    """;
    skillsBlock = extractEligibleSkillsBlock(resume)
    assert skillsBlock is None

    parsed = parseCoreFieldsFromResumeText(resume)
    assert bool(parsed['skillsRaw'])
    skills = parsed['skillsRaw'].split(', ')
    assert 'Kubernetes' in skills
    assert 'Docker' in skills
    assert 'Go' in skills

def test_14_a_resume_without_a_skills_section_and_no_explicit_skills_ret():
    resume = """
    Candidate Name
    Professional Experience
    Responsibilities:
    - Handled daily client communications and tracked deliverables.
    - Prepared status reports and documented meeting minutes.
    """;
    skillsBlock = extractEligibleSkillsBlock(resume)
    assert skillsBlock is None

    parsed = parseCoreFieldsFromResumeText(resume)
    assert parsed['skillsRaw'] is None

def test_15_different_valid_skills_heading_names_are_supported():
    headings = [
      'Skills',
      'Technical Skills',
      'Core Skills',
      'Key Skills',
      'Technical Competencies',
      'Core Technical Capabilities',
    ]

    for heading in headings:
      resume = f"""
    Jane Doe
    {heading}
    - Python, TypeScript, React
    
    Experience
    - Senior Developer at Acme Corp
    """;
      block = extractEligibleSkillsBlock(resume)
      assert bool(block)
      skills = extractWholeResumeSkills(resume, block)
      assert 'Python' in skills
      assert 'TypeScript' in skills
      assert 'React' in skills

def test_16_rejects_bullet_sentences_and_responsibilities_in_skills_sect():
    resume = """
    Technical Skills
    - Designed and developed new products.
    - Responsible for hardware testing and debugging.
    - Worked on various engineering projects.
    - Python
    - Docker
    """;
    skills = extractWholeResumeSkills(resume)
    assert 'Python' in skills
    assert 'Docker' in skills
    assert 'Designed and developed new products.' not in skills
    assert 'Responsible for hardware testing and debugging.' not in skills
    assert 'Worked on various engineering projects.' not in skills

def test_17_regression_test_6_summary_containing_mechanical_design_engin():
    resume = """
    Professional Summary
    Mechanical Design Engineer with experience in CAD/CAE software, product development and simulation.
    
    Technical Skills
    CATIA, SolidWorks
    
    Education
    B.Tech in Mechanical Engineering
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert parsed['technologies'] == 'Mechanical Design Engineer'
    assert parsed['technologiesRaw'] == 'Mechanical Design Engineer'
    assert parsed['role'] == 'Mechanical Design Engineer'

def test_18_regression_test_7_summary_containing_refinery_petrochemical_():
    resume = """
    Professional Summary
    A goal-oriented profession with nearly 12 years of experience in Refinery, Petrochemical and Chemical industry, worked experience in erection, pre commissioning, commissioning, production operation of some of the world's renowned plants.
    
    Education
    Diploma in Chemical Engineering
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert parsed['technologies'] == 'Refinery, Petrochemical and Chemical Industry'
    assert parsed['technologiesRaw'] == 'Refinery, Petrochemical and Chemical Industry'
    assert parsed['totalExperienceText'] == '12 years'

def test_19_domain_example_semiconductor_capital_equipment_battery_energ():
    resume = """
    Profile Summary
    Experienced professional specializing in semiconductor capital equipment and battery energy storage systems.
    
    Education
    B.E. in Electrical Engineering
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert parsed['technologies'] == 'Semiconductor Capital Equipment, Battery Energy Storage Systems'

def test_20_regression_test_8_summary_with_erection_pre_commissioning_co():
    resume = """
    Executive Profile
    Worked experience in erection, pre commissioning, commissioning, production operation of some of the world's renowned plants.
    
    Education
    B.Sc in Chemistry
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert parsed['technologies'] == 'Erection, Pre-commissioning, Commissioning and Production Operations'

def test_21_1_nearly_12_years_12_years():
    r = """Nearly 12 years of experience in petroleum engineering."""
    assert extractTotalExperienceInfo(r)['text'] == '12 years'

def test_22_2_7_years_7_years():
    r = """7+ years of experience in hardware engineering."""
    assert extractTotalExperienceInfo(r)['text'] == '7+ years'

def test_23_3_employment_dates_without_an_explicit_overall_experience():
    r = """
    Professional Experience
    Company A: Jan 2018 - Dec 2021
    Company B: Jan 2022 - Present
    """;
    assert extractTotalExperienceInfo(r)['text'] == ''
    assert extractTotalExperienceInfo(r)['years'] is None

def test_24_4_skills_section_containing_10_skills_maximum_10_individual_():
    r = """
    Technical Skills
    Java, Python, C++, Go, TypeScript, JavaScript, SQL, Rust, Ruby, PHP, Swift, Kotlin
    """;
    skills = extractWholeResumeSkills(r)
    assert len(skills) == 10
    assert skills[0] == 'Java'
    assert skills[9] == 'PHP'

def test_25_5_responsibilities_containing_duties_but_no_evidence_of_spec():
    r = """
    Work Experience
    Responsibilities:
    - Handled daily client communications, attended team standup meetings, and coordinated schedules
    """;
    parsed = parseCoreFieldsFromResumeText(r)
    assert parsed['skillsRaw'] is None

def test_26_6_summary_containing_mechanical_design_engineer_that_exact_d():
    r = """
    Professional Summary
    Mechanical Design Engineer with experience in CAD/CAE software.
    """;
    assert parseCoreFieldsFromResumeText(r)['technologies'] == 'Mechanical Design Engineer'

def test_27_7_summary_containing_refinery_petrochemical_and_chemical_ind():
    r = """
    Professional Summary
    A goal-oriented profession with nearly 12 years of experience in Refinery, Petrochemical and Chemical industry.
    """;
    assert parseCoreFieldsFromResumeText(r)['technologies'] == 'Refinery, Petrochemical and Chemical Industry'

def test_28_8_summary_containing_erection_pre_commissioning_commissionin():
    r = """
    Career Summary
    Worked experience in erection, pre commissioning, commissioning, production operation of various plants.
    """;
    assert parseCoreFieldsFromResumeText(r)['technologies'] == 'Erection, Pre-commissioning, Commissioning and Production Operations'

def test_29_9_resume_without_explicit_designation_domain_or_professional():
    r = """
    Candidate Name
    Email: cand@test.com
    Education: B.Tech
    """;
    assert parseCoreFieldsFromResumeText(r)['technologies'] or '' == ''

def test_30_1_resume_with_a_valid_dedicated_skills_section():
    resume = """
    Alice Smith
    Email: alice@example.com
    
    Technical Skills
    Python, React, PostgreSQL, Docker, AWS
    
    Experience
    Software Engineer at Acme Corp
    """;
    skills = extractWholeResumeSkills(resume)
    assert skills == ['Python', 'React', 'PostgreSQL', 'Docker', 'AWS']

def test_31_2_resume_with_no_skills_section_but_explicit_skills_in_the_s():
    resume = """
    Bob Johnson
    bob@example.com
    
    Professional Summary
    Experienced Software Engineer skilled in Python, Flask, and PostgreSQL with a background in designing REST APIs.
    
    Work Experience
    Engineer at Globex
    - Worked on backend systems.
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert bool(parsed['skillsRaw'])
    skills = parsed['skillsRaw'].split(', ')
    assert 'Python' in skills
    assert 'Flask' in skills
    assert 'REST APIs' in skills
    assert 'PostgreSQL' in skills

def test_32_3_resume_with_skills_explicitly_demonstrated_in_project_desc():
    resume = """
    Carol Danvers
    carol@example.com
    
    Technical Projects
    Predictive Analytics Pipeline:
    - Built machine learning models using Scikit-learn and XGBoost for patient outcome prediction.
    - Deployed models using FastAPI and Docker.
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert bool(parsed['skillsRaw'])
    skills = parsed['skillsRaw'].split(', ')
    assert 'Machine Learning' in skills
    assert 'Scikit-learn' in skills
    assert 'XGBoost' in skills
    assert 'FastAPI' in skills
    assert 'Docker' in skills

def test_33_4_resume_with_skills_explicitly_demonstrated_in_work_experie():
    resume = """
    David Miller
    david@example.com
    
    Work Experience
    Frontend Developer at Tech Corp (2021 - Present)
    - Experienced in designing responsive interfaces using React and Tailwind CSS.
    - Developed REST APIs and integrated GraphQL endpoints.
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert bool(parsed['skillsRaw'])
    skills = parsed['skillsRaw'].split(', ')
    assert 'React' in skills
    assert 'Tailwind CSS' in skills
    assert 'Responsive Web Design' in skills
    assert 'REST APIs' in skills
    assert 'GraphQL' in skills

def test_34_5_resume_containing_responsibilities_but_no_evidence_of_spec():
    resume = """
    Emily Davis
    emily@example.com
    
    Work Experience
    Operations Specialist (2020 - 2023)
    Responsibilities:
    - Responsible for attending daily standup meetings.
    - Managed team schedules and coordinated cross-functional meetings.
    - Liaised between clients and internal stakeholders to track deliverables.
    - Prepared weekly status updates and meeting minutes.
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert parsed['skillsRaw'] is None
    skills = extractWholeResumeSkills(resume)
    assert skills == []

def test_35_6_resume_with_skills_scattered_across_multiple_pages_or_colu():
    resume = """
    Frank Castle
    frank@example.com
    ------------------- Page Break / Column Split -------------------
    Summary:
    Proficient in Java and Spring Boot with experience in microservices.
    ------------------- Page Break / Column Split -------------------
    Projects:
    - Implemented real-time event streaming using Kafka and Redis.
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert bool(parsed['skillsRaw'])
    skills = parsed['skillsRaw'].split(', ')
    assert 'Java' in skills
    assert 'Spring Boot' in skills
    assert 'Kafka' in skills
    assert 'Redis' in skills

def test_36_7_resume_with_a_populated_skills_section_does_not_supplement():
    resume = """
    Grace Hopper
    grace@example.com
    
    Technical Skills
    COBOL, Fortran, Assembly
    
    Work Experience
    Senior Systems Architect
    Responsibilities:
    - Developed web services using Python, Docker, Kubernetes, and AWS.
    - Built reactive frontends with React and TypeScript.
    """;
    skills = extractWholeResumeSkills(resume)
    assert skills == ['COBOL', 'Fortran', 'Assembly']
    assert 'Python' not in skills
    assert 'Docker' not in skills
    assert 'Kubernetes' not in skills
    assert 'AWS' not in skills
    assert 'React' not in skills
    assert 'TypeScript' not in skills

def test_37_8_resume_with_duplicate_skills_and_more_than_10_candidate_sk():
    resume = """
    Henry Jekyll
    henry@example.com
    
    Technical Skills
    Python, Java, C++, Python, Go, Rust, Ruby, JavaScript, TypeScript, PHP, Swift, Kotlin, Java, Rust
    """;
    skills = extractWholeResumeSkills(resume)
    assert len(skills) == 10
    uniqueSkills = list(set(skills))
    assert len(uniqueSkills) == 10
    assert skills == [
      'Python',
      'Java',
      'C++',
      'Go',
      'Rust',
      'Ruby',
      'JavaScript',
      'TypeScript',
      'PHP',
      'Swift',
    ]

def test_38_9_resume_with_no_reliable_skill_evidence_does_not_infer_skil():
    resume = """
    Ian Malcolm
    ian@example.com
    
    Experience
    - Worked on a project for a banking client in financial services.
    - Managed customer relationships and oversaw office supplies.
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert parsed['skillsRaw'] is None
    skills = extractWholeResumeSkills(resume)
    assert skills == []

def test_39_10_pdf_and_docx_files_with_different_formatting_multi_line_t():
    resumeDocxTable = """
    Candidate Name: Jane Tech
    Email: jane@example.com
    
    | Technical Skills |
    | C++ | Python | Linux | Git | Docker | Jenkins |
    
    Professional Experience:
    Engineer at Corp
    """;
    skillsDocx = extractWholeResumeSkills(resumeDocxTable)
    assert 'C++' in skillsDocx
    assert 'Python' in skillsDocx
    assert 'Linux' in skillsDocx
    assert 'Git' in skillsDocx
    assert 'Docker' in skillsDocx
    assert 'Jenkins' in skillsDocx

    resumePdfBullets = """
    Candidate Name: Mark Code
    Summary
    • Proficient in Go and Kubernetes
    ▪ Developed web applications with Vue.js and MongoDB
    * Implemented authentication using JWT
    """;
    parsedPdf = parseCoreFieldsFromResumeText(resumePdfBullets)
    assert bool(parsedPdf['skillsRaw'])
    pdfSkills = parsedPdf['skillsRaw'].split(', ')
    assert 'Go' in pdfSkills
    assert 'Kubernetes' in pdfSkills
    assert 'Vue.js' in pdfSkills
    assert 'MongoDB' in pdfSkills
    assert 'JWT Authentication' in pdfSkills

def test_40_1_explicit_experience_in_the_summary():
    resume = """
    Professional Summary
    Results-driven Senior Full Stack Developer with 8 years of professional experience building scalable web apps.
    """;
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '8 years'
    assert info['years'] == 8

def test_41_2_explicit_experience_in_the_work_experience_section():
    resume = """
    Work Experience
    Total Experience: 6 years
    Company A - Software Engineer (2018 - 2024)
    """;
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '6 years'
    assert info['years'] == 6

def test_42_3_values_containing():
    resume = """
    Executive Profile
    IT Architect offering 7+ years of experience in enterprise systems design.
    """;
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '7+ years'
    assert info['years'] == 7

def test_43_4_decimal_values_such_as_4_5_years():
    resume = """
    Profile
    Software Engineer with 4.5 years of experience in Python and cloud services.
    """;
    info = extractTotalExperienceInfo(resume)
    assert info['text'] == '4.5 years'
    assert info['years'] == 4

def test_44_5_qualifiers_such_as_nearly_over_and_more_than_stripped_to_c():
    rNearly = """Nearly 12 years of experience in Refinery and Petrochemical industry."""
    assert extractTotalExperienceInfo(rNearly)['text'] == '12 years'

    rOver = """Over 7 years of experience in mechanical engineering."""
    assert extractTotalExperienceInfo(rOver)['text'] == '7 years'

    rMoreThan = """More than 10 years of professional experience."""
    assert extractTotalExperienceInfo(rMoreThan)['text'] == '10 years'

    rApprox = """Approximately 8 years of experience."""
    assert extractTotalExperienceInfo(rApprox)['text'] == '8 years'

    rAbout = """About 5 years of experience in backend development."""
    assert extractTotalExperienceInfo(rAbout)['text'] == '5 years'

def test_45_6_experience_stated_on_a_later_page():
    resumeMultiPage = """
    Candidate Name
    candidate@example.com
    Education: B.Tech in Computer Science, 2016
    -------------------- Page Break --------------------
    Technical Skills: Java, Spring Boot, Microservices
    -------------------- Page Break --------------------
    Work Experience
    Total Experience: 6 years
    Senior Developer at Tech Corp
    """;
    info = extractTotalExperienceInfo(resumeMultiPage)
    assert info['text'] == '6 years'
    assert info['years'] == 6

def test_46_7_employment_dates_without_an_explicit_total_returns_empty_s():
    resumeDatesOnly = """
    Work Experience
    Software Engineer at Acme Corp: 2018 - 2021
    Senior Engineer at Beta LLC: 2021 - 2025
    """;
    info = extractTotalExperienceInfo(resumeDatesOnly)
    assert info['text'] == ''
    assert info['years'] is None

def test_47_8_multiple_conflicting_experience_statements_resolves_determ():
    resumeConflict = """
    Professional Summary
    Total Experience: 8 years in cloud architecture.
    
    Experience History
    Total Experience: 6 years in consulting.
    """;
    info = extractTotalExperienceInfo(resumeConflict)
    # Deterministic rule: earliest/primary statement wins
    assert info['text'] == '8 years'
    assert info['years'] == 8

    resumePlusConflict = """
    Summary: 8 years of total experience.
    Experience: 8+ years of total experience.
    """;
    infoPlus = extractTotalExperienceInfo(resumePlusConflict)
    # Preserves explicit '+'
    assert infoPlus['text'] == '8+ years'

def test_48_9_pdf_and_docx_formatting_variations_tables_colons_bullet_sy():
    tableFormat = """
    | Total Experience | 6.5 Years |
    | Current Location | Bangalore |
    """;
    assert extractTotalExperienceInfo(tableFormat)['text'] == '6.5 years'

    bulletFormat = """
    • Total Experience: 7+ yrs
    • Highest Qualification: M.Tech
    """;
    assert extractTotalExperienceInfo(bulletFormat)['text'] == '7+ years'

    multiLineFormat = """
    Total Experience:
    10 years
    """;
    assert extractTotalExperienceInfo(multiLineFormat)['text'] == '10 years'

    twoColumnFormat = """
    Total Experience   5 Years
    Location           Hyderabad
    """;
    assert extractTotalExperienceInfo(twoColumnFormat)['text'] == '5 years'

def test_49_test_b_missing_skills_section_developed_a_web_application_us():
    resume = """
    Alex Morgan
    alex@example.com
    
    Work Experience
    Full Stack Developer
    - Developed a web application using Python, Flask and PostgreSQL.
    """;
    skills = extractWholeResumeSkills(resume)
    assert skills == ['Python', 'Flask', 'PostgreSQL']

def test_50_test_c_cad_resume_used_autocad_and_cad_software_to_design_me():
    resume = """
    Sam Design
    sam@example.com
    
    Summary
    Used AutoCAD and CAD software to design mechanical components.
    """;
    skills = extractWholeResumeSkills(resume)
    assert 'AutoCAD' in skills
    assert 'CAD' in skills

def test_51_test_d_spoken_languages_languages_telugu_hindi_technical_ski():
    resume = """
    Languages: Telugu, Hindi. Technical Skills: Python, SQL.
    """;
    skills = extractWholeResumeSkills(resume)
    assert skills == ['Python', 'SQL']
    assert 'Telugu' not in skills
    assert 'Hindi' not in skills

def test_52_test_f_no_reliable_evidence():
    resume = """
    John Nothing
    john@nothing.com
    
    Summary
    Hard working individual seeking opportunities.
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    skills = extractWholeResumeSkills(resume)
    assert skills == []
    assert parsed['skillsRaw'] is None
    assert parsed['technologies'] or '' == ''
    assert parsed['technologiesRaw'] or '' == ''

def test_53_fallback_ml_example_performed_data_preprocessing_and_model_e():
    resume = """
    Taylor Data
    taylor@example.com
    
    Work Experience
    Data Scientist
    - Performed data preprocessing and model evaluation using Python and Scikit-learn.
    """;
    skills = extractWholeResumeSkills(resume)
    assert 'Python' in skills
    assert 'Scikit-learn' in skills
    assert 'Data Preprocessing' in skills
    assert 'Model Evaluation' in skills

def test_54_technologies_field_handles_designations_with_attached_experi():
    r1 = """Python Developer - 4 years"""
    assert parseCoreFieldsFromResumeText(r1)['technologies'] == 'Python Developer'

    r2 = """CAD Designer with experience using AutoCAD."""
    assert parseCoreFieldsFromResumeText(r2)['technologies'] == 'CAD Designer'

    r3 = """AI/ML Engineer"""
    assert parseCoreFieldsFromResumeText(r3)['technologies'] == 'AI/ML Engineer'

    r4 = """Worked in CAD for 6 years"""
    assert parseCoreFieldsFromResumeText(r4)['technologies'] or '' == ''

    r5 = """4 years of Python"""
    assert parseCoreFieldsFromResumeText(r5)['technologies'] or '' == ''

    r6 = """Worked with Python, SQL and machine learning."""
    assert parseCoreFieldsFromResumeText(r6)['technologies'] or '' == ''

def test_55_test_a_provided_global_mobility_resume():
    resume = """
    Shadiq Khan B
    Global Mobility Immigration
    +91 9876543210
    shadiq@example.com
    
    Summary
    Global Mobility Immigration professional with 3+ years of experience expertise in UK and Germany mobility operations and cross-border compliance.
    
    Skills
    Global mobility management, Relocation and cross border compliance, visa processing for business purpose, tax documents, international payroll process, vendor management, stakeholders management, immigration risk management, process improvement
    
    Certifications
    Global Mobility Specialist (GMS)
    
    Languages
    English, Hindi, Telugu
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    skills = extractWholeResumeSkills(resume)

    # 1. Skills contain complete professional skill phrases
    assert skills == [
      'Global Mobility Management',
      'Relocation and Cross-Border Compliance',
      'Visa Processing',
      'Tax Documentation',
      'International Payroll Processing',
      'Vendor Management',
      'Stakeholder Management',
      'Immigration Risk Management',
      'Process Improvement',
    ]

    # 2. 'For', 'And', 'Cross', and 'Border' are not returned as separate skills
    prohibitedTokens = ['For', 'And', 'Cross', 'Border', 'Visa', 'Processing', 'Management']
    for token in prohibitedTokens:
      assert token not in skills

    # 3. Certifications and language names are excluded
    assert 'Global Mobility Specialist' not in skills
    assert 'GMS' not in skills
    assert 'English' not in skills
    assert 'Hindi' not in skills
    assert 'Telugu' not in skills

    # 4. Technologies equals 'Global Mobility Immigration'
    assert parsed['technologies'] == 'Global Mobility Immigration'
    assert parsed['technologiesRaw'] == 'Global Mobility Immigration'
    assert parsed['technologies'] != 'UK, Germany Mobility Operations'

def test_56_test_b_software_developer_resume():
    resume = """
    Jane Doe
    Java Full Stack Developer
    jane.doe@example.com
    +1 555-123-4567
    
    Summary
    Passionate Java Full Stack Developer with 5 years of experience.
    
    Skills
    Java, Spring Boot, SQL, React
    
    Experience
    Software Engineer at TechCorp
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    skills = extractWholeResumeSkills(resume)

    assert skills == ['Java', 'Spring Boot', 'SQL', 'React']
    assert parsed['technologies'] == 'Java Full Stack Developer'

def test_57_test_c_designation_only_in_summary():
    resume = """
    Alex Smith
    alex.smith@example.com
    +1 555-987-6543
    
    Summary
    Data Analyst with 4 years of experience turning complex data into actionable insights.
    
    Experience
    Worked at Analytics Inc.
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert parsed['technologies'] == 'Data Analyst'

def test_58_test_d_designation_only_in_employment_history():
    resume = """
    Michael Brown
    michael.brown@example.com
    +1 555-000-1111
    
    Summary
    Professional with over 6 years of expertise across modern industries.
    
    Experience
    DevOps Engineer at Cloud Solutions Inc.
    - Managed Kubernetes clusters and CI/CD pipelines.
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert parsed['technologies'] is None
    assert parsed['role'] is None

def test_59_test_e_no_explicit_designation():
    resume = """
    Robert White
    robert.white@example.com
    +1 555-222-3333
    
    Summary
    Passionate professional with hands-on background in client delivery and project execution.
    
    Experience
    Worked on various deliverables and managed timelines.
    """;
    parsed = parseCoreFieldsFromResumeText(resume)
    assert parsed['technologies'] or '' == ''

def test_60_test_f_no_dedicated_skills_section():
    resume = """
    Sarah Green
    sarah.green@example.com
    +1 555-444-5555
    
    Experience
    Web Developer at Innovate LLC
    - Developed full-stack web applications using Python, Django and PostgreSQL.
    - Responsible for daily operations and client communications.
    """;
    skills = extractWholeResumeSkills(resume)
    assert 'Python' in skills
    assert 'Django' in skills
    assert 'PostgreSQL' in skills

    # Never return sentences, arbitrary tokens, or duties
    assert not any('responsible for' in s.lower() for s in skills)
    assert not any('daily operations' in s.lower() for s in skills)
    assert not any('client communications' in s.lower() for s in skills)
    assert not any(len(s.split(" ")) > 4 for s in skills)



# ============================================================================
# Tests calling applyEvidenceLock
# ============================================================================
from src.metaforgeParser import applyEvidenceLock
from src.parseCoreResumeFields import extractWholeResumeSkills


def test_apply_evidence_lock_strictly_sets_total_experience_to_explicit_cleaned_value():
    resume_with_exp = "Over 5 years of experience in hardware design.\nCompany A: 2018 - 2023"
    candidate = {
        'candidateName': 'Test Candidate',
        'email': 'test@example.com',
        'contactNumber': None,
        'linkedinUrl': None,
        'highestQualification': None,
        'skillsRaw': None,
        'technologiesRaw': None,
        'totalExperience': 'Over 5 years',
        'relevantExperience': None,
        'currentEmployer': None,
        'sourceFile': 'resume.txt',
        'parser': 'metaforge',
    }
    locked = applyEvidenceLock(candidate, resume_with_exp)
    assert locked['totalExperience'] == '5 years'

    dates_only_resume = """
Work Experience
Company A: January 2020 – December 2022
Company B: January 2023 – Present
"""
    candidate['totalExperience'] = '4+ years'
    locked_dates = applyEvidenceLock(candidate, dates_only_resume)
    assert locked_dates['totalExperience'] == ''


def test_populated_skills_section_not_supplemented_by_extra_technologies():
    resume = """
John Doe
Software Engineer
Email: john@example.com

Technical Skills
Python, Django

Job Responsibilities
- 3D CAD Modeling & Detailing
- Sheet Metal & Weldment Design
- Design for Manufacturing (DFM)
- Developed responsive web applications using React and Node.js
"""
    mock_candidate = {
        'candidateName': 'John Doe',
        'email': 'john@example.com',
        'contactNumber': None,
        'linkedinUrl': None,
        'highestQualification': None,
        'skillsRaw': 'Python, Django, React, Node.js, DFM, Sheet Metal Design',
        'technologiesRaw': None,
        'totalExperience': None,
        'relevantExperience': None,
        'currentEmployer': None,
        'sourceFile': 'resume.txt',
        'parser': 'metaforge',
    }
    locked = applyEvidenceLock(mock_candidate, resume)
    assert locked['skillsRaw'] == 'Python, Django'


def test_regression_test_9_resume_without_explicit_designation_returns_empty_string():
    resume = """
John Doe
john.doe@example.com
+91 9876543210

Education
B.Tech in Computer Science
"""
    candidate = {
        'candidateName': 'John Doe',
        'email': 'john.doe@example.com',
        'contactNumber': '+91 9876543210',
        'linkedinUrl': None,
        'highestQualification': 'B.Tech in Computer Science',
        'skillsRaw': None,
        'technologiesRaw': None,
        'totalExperience': '',
        'relevantExperience': None,
        'currentEmployer': None,
        'sourceFile': 'resume.txt',
        'parser': 'metaforge',
    }
    locked = applyEvidenceLock(candidate, resume)
    assert (locked.get('technologies') or '') == ''
    assert (locked.get('technologiesRaw') or '') == ''


def test_section_5_test_a_provided_shiva_boda_resume():
    resume = """
Shiva Boda
shivaboda@example.com
+91 9876543210

Education
B.Tech in Computer Science

Technical Skills
Programming Languages: Python, SQL
Database: MS SQL Server

Projects
- Machine Learning Project
- The project development process
- Gained hands-on experience
- Evaluation
- Pandas, Scikit-learn

Certifications
- AI & Machine Learning — Edunet Foundation
- ServiceNow Micro-Certification
- SQL Certification — Intellipaat
- Python Fundamentals — Great Learning

Strengths
Quick Learner, Problem Solving, Teamwork, Communication

Languages
Telugu, Hindi, English
"""
    skills = extractWholeResumeSkills(resume)
    locked = applyEvidenceLock(
        {
            'candidateName': 'Shiva Boda',
            'email': 'shivaboda@example.com',
            'contactNumber': '+91 9876543210',
            'linkedinUrl': None,
            'highestQualification': 'B.Tech',
            'totalExperience': '',
            'relevantExperience': None,
            'skillsRaw': 'Python, SQL, MS SQL Server, Internship, AI, The project development process, Gained hands-on, Evaluation',
            'technologiesRaw': '- The project development process',
            'currentEmployer': None,
            'sourceFile': 'shiva_boda.pdf',
            'parser': 'metaforge',
            'role': 'AI & Machine Learning Intern',
        },
        resume,
    )

    assert skills == ['Python', 'SQL', 'MS SQL Server']
    assert locked['skillsRaw'] == 'Python, SQL, MS SQL Server'

    prohibited = [
        'Internship',
        'AI & Machine Learning Intern',
        'The project development process',
        'Gained hands-on experience',
        'Evaluation',
        'Pandas',
        'Scikit-learn',
        'Certifications',
        'Quick Learner',
        'Problem Solving',
        'Teamwork',
        'Communication',
        'Telugu',
        'Hindi',
        'English',
    ]
    for p in prohibited:
        assert p not in skills
        assert p not in (locked['skillsRaw'] or '')

    assert (locked.get('technologies') or '') == ''
    assert (locked.get('technologiesRaw') or '') == ''


def test_section_5_test_e_explicit_role_and_years():
    resume = """
Java Developer with 4 years of experience.
"""
    locked = applyEvidenceLock(
        {
            'candidateName': 'Test Cand',
            'email': 'test@example.com',
            'contactNumber': None,
            'linkedinUrl': None,
            'highestQualification': None,
            'totalExperience': '4 years',
            'relevantExperience': None,
            'skillsRaw': 'Java',
            'technologiesRaw': 'Java Developer with 4 years of experience',
            'currentEmployer': None,
            'sourceFile': 'test.pdf',
            'parser': 'metaforge',
            'role': 'Java Developer with 4 years of experience',
        },
        resume,
    )
    assert locked['technologies'] == 'Java Developer'
    assert locked['technologiesRaw'] == 'Java Developer'


def test_section_5_test_g_regression_protection_unrelated_fields_intact():
    resume = """
Name: Shadiq Khan B
Global Mobility Immigration
+91 9876543210
shadiq.khan@gmail.com
https://linkedin.com/in/shadiqkhan

Summary
Global Mobility Immigration professional with 3+ years of experience in immigration compliance.

Education
Master of Business Administration (MBA) in Human Resources
B.Com in Commerce

Skills
Global mobility management, Relocation and cross border compliance

Certifications
Global Mobility Specialist (GMS)

Languages
English, Hindi, Telugu
"""
    from src.parseCoreResumeFields import parseCoreFieldsFromResumeText
    parsed = parseCoreFieldsFromResumeText(resume)
    candidate = {
        'candidateName': parsed['candidateName'],
        'email': parsed['email'],
        'contactNumber': parsed['contactNumber'],
        'linkedinUrl': parsed['linkedinUrl'],
        'highestQualification': parsed['highestQualification'],
        'skillsRaw': parsed['skillsRaw'],
        'technologiesRaw': parsed['technologiesRaw'],
        'technologies': parsed['technologies'],
        'totalExperience': parsed['totalExperienceText'] or '',
        'relevantExperience': None,
        'currentEmployer': None,
        'sourceFile': 'shadiq_resume.pdf',
        'parser': 'metaforge',
        'role': parsed['technologies'],
    }
    locked = applyEvidenceLock(candidate, resume)
    assert locked['candidateName'] == 'Shadiq Khan B'
    assert locked['email'] == 'shadiq.khan@gmail.com'
    assert locked['contactNumber'] == '+919876543210'
    assert locked['totalExperience'] == '3+ years'
    assert locked['highestQualification'] == 'Master of Business Administration (MBA) in Human Resources'
    assert locked['technologies'] == 'Global Mobility Immigration'
    assert locked['skillsRaw'] == 'Global Mobility Management, Relocation and Cross-Border Compliance'

