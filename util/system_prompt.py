from typing_extensions import Final


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

prompt_generate_summary = ("""
You are an expert HR Analyst. Your job is to extract structured data from the job description below using the format shown.

Do not return any explanations, comments, or schema definitions. Respond ONLY with a valid JSON object that fills in the structure.

Job Description:
---
{jd}
---

Expected Output Format:
{format_schema}
""" )

agg_prompt = ("""
You are an experienced analyst. Given multiple structured outputs for the same JD, combine them into one consistent and complete output.

JSONs:
{reflected_outputs}
              
Final output must follow the exact same schema and include all valid points. Merge duplicates where possible.
""")
