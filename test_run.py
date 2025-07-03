from util.llm_factory import LLMFactory
from util.system_prompt import prompt_input

from typing import Optional


def generate_job_description(
    job_title: str,
    location: str,
    reporting_relationship: str,
    function: str,
    role_overview: str,
    key_responsibilities: str,
    qualifications: str,
    skills_and_competencies: str,
    our_company: Optional[str] = None,
    our_culture: Optional[str] = None,
) -> Optional[str]:
    """
    Generates a job description using the provided job details via LLM.

    Args:
        All job-related fields provided via FastAPI request

    Returns:
        Generated job description string or None if generation fails
    """
    try:

        prompt_input_jd = prompt_input.format(
            job_title=job_title,
            location=location,
            reporting_relationship=reporting_relationship,
            function=function,
            role_overview=role_overview,
            key_responsibilities=key_responsibilities,
            qualifications=qualifications,
            skills_and_competencies=skills_and_competencies,
            our_company=our_company,
            our_culture=our_culture,
        )

        # Call LLM
        response = LLMFactory.invoke(
            # system_prompt=prompt_input_jd,
            human_message=prompt_input_jd,
            temperature=0.4,
            local_llm=False,
        )

        return response.content.strip()

    except Exception as e:
        print(f"Error generating job description: {e}")
        return None