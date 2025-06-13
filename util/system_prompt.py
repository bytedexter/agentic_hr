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

prompt_categorize_experience = (
    "Based on the following job application, categorize the candidate as 'Entry-level', 'Mid-level' or 'Senior-level'. "
    "Anyone with experience of more than 7 years is considered 'Senior-level'. "
    "Respond with one of: 'Entry-level', 'Mid-level', or 'Senior-level'.\n\nApplication:\n{application}"
)

prompt_assess_skillset = (
    "Based on the job application for a Python Developer, assess the candidate's skillset. "
    "Respond with either 'Match' or 'No Match'.\n\nApplication:\n{application}"
)

prompt_assess_skillset_new = "Just return the role as SDE nothing else."

prompt_email_details = "From the {application},extract the reciever email that is the mail id given in the resume and store it.Only return the email id as a single stirng nothing else.remove the \n and the name with it"

prompt_email_details_new = "Only return the name of the candidate as given in the application {application}.And nothing else should be returned other than the name of the candidate."

prompt_schedule_interview = (
    "Generate the email subject and body for Candidate has been shortlisted for an HR interview by extracting information regarding the candidate from the given application {application} "
    "Save the email subject in sub and body in message."
    "Give the output as a json with keys sub and message."
)

prompt_escalate_to_recruiter = (
    "Generate the email subject and body for Candidate has senior-level experience but doesn't match job skills so the conadidature is escalated to the recruiter by extracting information regarding the candidate from the given application {application} "
    "Save the email subject in sub and body in message."
    "Give the output as a json with keys sub and message."
)

prompt_rejection = (
    "Generate the email subject and body for Candidate doesn't meet JD and has been rejected. by extracting information regarding the candidate from the given application {application} "
    "Save the email subject in sub and body in message."
    "Give the output as a json with keys sub and message."
)
