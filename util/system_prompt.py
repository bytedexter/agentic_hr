<<<<<<< HEAD
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
=======
generate_goals_prompt = (
    "As the manager for the {role} position, generate exactly 3 clear, concise, and measurable performance goals. "
    "Keep them relevant to core responsibilities. Return only bullet points, no intro or explanation."
)
acknowledgment_prompt = (
    "Hi {name}, your goals are: {tasks}. "
    "Do you accept them? Reply with 'yes' or 'no' followed by a brief reason (one sentence max)."
)
feedback_prompt = (
    "You are {name}, working as a {role}. You were assigned these goals: {tasks}. "
    "Write 2-3 lines of honest feedback on your experience—be constructive, role-specific, and realistic."
)
report_generation_prompt = (
    "Write a formal performance summary for {name} based on:\n"
    "- Goals: {tasks}\n"
    "- Acknowledged: {acknowledged}\n"
    "- Feedback: {feedback}\n\n"
    "Keep it structured, to the point, and split into clear sections (e.g., Goals, Feedback Summary, Conclusion)."
)
>>>>>>> 384fd5b (Initial commit: Performance management flow)
