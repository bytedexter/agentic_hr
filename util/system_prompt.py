generate_offer_letter_prompt = (
    "Please generate a professional offer letter for {name}, "
    "joining as {role} from {start_date}. Use a formal and welcoming tone."
    "Include a placeholder for salary and benefits. Conclude with a warm closing."
    "Ensure the main sections are clearly distinguishable with standard markdown formatting."
    "Crucially, mention that they must click the unique link provided in the email to accept/reject the offer."
    "Do NOT ask for a reply to this email for acceptance."
)

onboarding_completion_success_email_and_first_day_orientation_prompt = (
    "Generate a warm and welcoming message for a new hire named {name} "
    "who has just completed their onboarding for the {role} position. "
    "The message should have two parts:\n\n"
    "1.  **Welcome Message:** A short, heartfelt message congratulating them and expressing excitement for them joining the team.\n\n"
    "2.  **First Day Orientation:** A clear, bulleted list of instructions for their first day. Include points like:\n"
    "    - Arrival Time (e.g., 9:30 AM)\n"
    "    - Office Address (use a placeholder like '[Office Address]')\n"
    "    - Who to ask for at the reception (e.g., 'the HR Manager')\n"
    "    - What to bring (e.g., a notebook, a form of ID)\n"
    "    - A brief mention of what to expect (e.g., 'setting up your workstation and meeting the team').\n\n"
    "Use markdown for formatting."
)