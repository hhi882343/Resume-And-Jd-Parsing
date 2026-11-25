"""
Prompt template and builder for Gemini extraction.
"""

EXTRACTION_PROMPT = """You are a world-class resume parsing engine for Metaforge IT Solutions.
Extract the fields below. THE RESUME IS THE SOURCE OF TRUTH. Follow STRICT SOURCE EVIDENCE RULES per field.

FIELD 1 — full_name: Candidate name from top of resume.
FIELD 2 — contact: All phone numbers. Format: +[CC] [local] with ONE space after country code. Multiple → join with " / ".
FIELD 3 — email: Primary email address.
FIELD 4 — linkedin: LinkedIn URL/handle or null.

FIELD 5 — qualification:
  • SINGLE highest legitimate academic degree with course/branch/specialization from education context ONLY.
  • Examples: "B.Tech in Computer Science and Engineering", "B.Tech (CSE)", "PGDM in IT Projects Management", "M.Tech in Computer Science", "MBA - Finance".
  • NEVER include university, college, school, year, marks, GPA, location, duration, or training provider.
  • NEVER classify certifications/training as academic degrees (exclude Scrum Master, PMP, AWS Certified, Azure Administrator, ISTQB, Six Sigma, etc.).
  • "Scrum Master" or "Master Trainer" is NOT a Master's degree.
  • Return null if no legitimate academic degree is found.

FIELD 6 — total_experience:
  • Scan the entire resume (summary, profile, work experience, headers, tables) for an explicitly stated total number of years of professional experience.
  • Extract the stated numeric value and unit (e.g. "12 years", "7 years", "7+ years", "8+ years", "4.5 years", "10 years", "36 months").
  • Preserve the number and decimal precision as written (e.g. "4.5 years").
  • Preserve the "+" sign ONLY if explicitly present (e.g. "8+ years", "7+ years").
  • REMOVE descriptive qualifier words such as "overall", "nearly", "approximately", "about", "over", "more than", "having", "close to", and "experience of". E.g. "Nearly 12 years of experience" → "12 years", "Over 7 years of experience" → "7 years", "More than 10 years of professional experience" → "10 years".
  • NEVER calculate, estimate, infer, or derive experience from employment dates, job periods, education dates, or current date.
  • Return null if not explicitly stated.

FIELD 6b — work_periods:
  • Return []. Do NOT calculate or derive total experience from employment dates.

FIELD 7 — skills:
  • Extract a MAXIMUM OF 10 individual skills following STRICT source priority:
  • PRIMARY: Extract from the resume's dedicated Skills section if present and populated (Skills, Technical Skills, Core Skills, Key Skills, Professional Skills, Relevant Skills, Areas of Expertise, Competencies, Software Skills, Tools and Technologies, Programming Languages, IT Skills).
  • The dedicated Skills section is AUTHORITATIVE. NEVER supplement or replace its contents with technologies mentioned in projects, internships, work experience, or certifications when the dedicated section is populated.
  • Preserve the original skill wording wherever practical. NEVER split a multiword skill into individual words or tokens (e.g. "Global mobility management" must remain "Global Mobility Management", NEVER "Global", "Mobility").
  • Comma is a delimiter between complete skills, NOT a delimiter for word-level splitting.
  • For parenthetical skills like "SQL (MS SQL Server)", extract both: "SQL" and "MS SQL Server".
  • FALLBACK: If NO dedicated Skills section exists (or it is genuinely empty or unusable), extract explicitly evidenced skills from other resume sections in this priority order:
    1. Professional Summary / Profile / Career Summary / Objective
    2. Work experience and responsibilities
    3. Technical project descriptions
    4. Education and academic project descriptions
    5. Other relevant sections containing explicit competencies
  • NEVER extract section headings (e.g. "Internship", "Projects", "Education", "Certifications", "Strengths", "Languages", "Achievements", "Awards", "Professional Summary", "Summary", "Profile", "Personal Details").
  • NEVER extract generic phrases or duty descriptions (e.g. "The project development process", "Gained hands-on experience", "Learned the fundamentals", "Evaluation").
  • NEVER extract articles, prepositions, or single words like "For", "And", "Cross", "Border" when they are fragments of longer skills.
  • NEVER extract spoken or mother tongue languages (e.g. "Telugu", "Hindi", "Tamil", "English", "Spanish") as technical or professional skills.
  • NEVER extract soft skills or personal traits (e.g. "Quick Learner", "Problem Solving", "Teamwork", "Communication").
  • NEVER extract certifications or certification titles as skills (e.g. "ServiceNow Micro-Certification", "Global Mobility Specialist (GMS)", "Edunet Foundation").
  • Output must contain individual skill names only (e.g. "React", "Node.js", "Express", "MongoDB", "Global Mobility Management", "Relocation and Cross-Border Compliance"), NEVER bullet points, complete sentences, job duties, or responsibilities.
  • Deduplicate and return an array of strings with AT MOST 10 items. Return [] if no reliable skills can be identified.

FIELD 7b — technology:
  • Return [].

FIELD 8 — role:
  • Extract the role only from the text below the name or from the summary. Never use job titles from the experience section.
  • STRICT TWO-SOURCE RULE:
    1. Priority 1 (Header - line(s) directly below candidate's name): First identify the professional designation mentioned directly below, beside, or near the candidate's name across all formats (e.g. "Full Stack Developer", "Data Analyst | Python", "Quality Engineer").
       - Clean separators (|, –, —, -, /, commas): Extract only the primary job title (e.g. "Quality Inspector – In-Process & Final Inspection | Aerospace Manufacturing" → "Quality Inspector", "Quality Engineer | Aerospace Specialist" → "Quality Engineer", "Senior Java Developer | Backend Engineer" → "Senior Java Developer").
       - DOMAIN PHRASE CONVERSION: If the header contains domain/discipline phrases instead of explicit job titles, convert the FIRST one to a professional role (e.g. "QUALITY ENGINEERING | QUALITY INSPECTION | FIRST ARTICLE INSPECTION" → "Quality Engineer", "DATA ENGINEERING | DATA ANALYSIS" → "Data Engineer", "SOFTWARE ENGINEERING" → "Software Engineer", "QUALITY CONTROL" → "Quality Control Engineer").
       - Preserve seniority levels ("Senior", "Junior", "Lead", "Principal", "Associate"). Prefer the first primary designation; do NOT combine multiple titles.
       - HEADER OVERRIDES SUMMARY: If the header contains a designation or domain phrase, it takes highest priority.
    2. Priority 2 (Summary / Profile / Objective / About section): If no designation is available in the header near the candidate's name, analyze the Summary / Profile / Objective / About section (e.g. "Software engineer with 3 years of experience...").
       - Example: "Experienced professional with 5 years of experience in Java application development and Spring Boot." → Expected: "Java Developer".
       - Example: "Professional with 4 years in quality inspection and aerospace manufacturing." → Expected: "Quality Inspector".
       - Example: "Quality Engineering and Quality Inspection professional with 8+ years of experience." → Expected: "Quality Engineer".
       - Distinguish professional designations from educational qualifications, degrees, skills, and industry domains. Never extract an educational degree (e.g. "Mechanical Engineer", "B.Tech in Computer Science") merely because it appears in the summary when describing academic background.
  • FALLBACK: If no role is found in the header or summary, return null. Do NOT fall back to the Experience section.
  • DO NOT extract the role from the Experience / Work Experience / Professional Experience / Employment History section (or any synonym such as Career History, Work History, Internships). Ignore job titles, company names, and dates listed there.
  • Extract only ONE primary designation.
  • NEVER include numeric years of experience (e.g. "5 years").
  • NEVER return section headings (e.g. "Professional Summary", "Achievements", "Awards", "Skills", "Personal Details") as the role.
  • NEVER return company names, duties, project bullet points, or full sentences.
  • NEVER return equipment or instrument names from "Equipment Handled" or "Tools" sections as the role (e.g. "Surface Roughness Tester", "Roundness Tester", "Gear Roll Tester", "Profile Projector" are equipment, NOT job titles).

FIELD 9 — location:
  • Candidate's city, state, or country if explicitly stated (e.g. "Bangalore, Karnataka", "Hyderabad", "Dallas, TX").
  • Return null if no explicit location is stated.

FIELD 10 — current_employer:
  • Candidate's current or most recent organization or employer name if explicitly stated (e.g. "Infosys", "Wipro", "TCS"). Return null if not explicitly stated.

RULES: Extract only explicit content from the resume. Deduplicate. null for missing strings, [] for arrays.
OUTPUT: Single valid JSON only. No markdown.
{"full_name":null,"contact":null,"email":null,"linkedin":null,"location":null,"qualification":null,"total_experience":null,"work_periods":[],"skills":[],"technology":[],"role":null,"current_employer":null}"""


def build_text_prompt(resume_text: str) -> str:
    separator = '=' * 40
    return f"{EXTRACTION_PROMPT}\n\n{separator}\nRESUME\n{separator}\n{resume_text}"


buildTextPrompt = build_text_prompt

