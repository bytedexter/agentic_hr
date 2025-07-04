prompt_input = """
You are an expert HR professional tasked with creating a compelling, industry-standard job description for a real company. Use the details provided below to craft a clear, attractive, and professional job description suitable for posting on major job boards. Ensure the language is engaging, inclusive, and accurately reflects the role and company.

Include the following sections, using the dynamic variables as content:

- **Job Title**: {job_title}
- **Location**: {location}
- **Reporting To**: {reporting_relationship}
- **Department/Function**: {function}
- **Role Overview**: {role_overview}
- **Key Responsibilities**: {key_responsibilities}
- **Qualifications**: {qualifications}
- **Skills & Competencies**: {skills_and_competencies}
- **About the Company**: {our_company}
- **Our Culture**: {our_culture}

Format the job description as companies do in real job postings. Make sure it is detailed, professional, and encourages qualified candidates to apply.
"""