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
