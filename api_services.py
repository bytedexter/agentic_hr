from fastapi import APIRouter, HTTPException, status
from base_requests import GenerateContentRequest, GenerateContentResponse
from util.system_prompt import agg_prompt
from util.llm_factory import LLMFactory
from test_run import invoke_llm_with_reflection
import json
import re
import logging

def scan_job_description(jd: str, count: int, config_path: str) -> dict:
    # Use the provided config_path, fallback to default if None
    count=3
    try:
        with open(config_path, 'r') as f:
            format_schema = f.read()
    except FileNotFoundError:
        raise ValueError(f"Configuration file not found: {config_path}")
    except Exception as e:
        raise ValueError(f"Error reading configuration file: {e}")
    reflections = invoke_llm_with_reflection(jd, format_schema)

    aggregation_prompt = agg_prompt.format(reflected_outputs=json.dumps(reflections, indent=2)).strip()
    final_result = LLMFactory.create_llm_instance(temperature=0.2, local_llm=False).invoke(aggregation_prompt)

    # Try to extract JSON using regex if LLM adds extra text
    match = re.search(r"\{.*\}", final_result.content, re.DOTALL)
    if match:
        cleaned_json = match.group(0)
        return json.loads(cleaned_json)
    else:
        raise ValueError("LLM response did not contain valid JSON.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_router = APIRouter(tags=["HR API Services"])

@api_router.post(
    "/scan",
    response_model=GenerateContentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid Job Description"},
        422: {"description": "Unprocessable Job Description"},
    },
)
async def generate_content(request: GenerateContentRequest) -> GenerateContentResponse:
    try:
        logger.info("Generating content with Job Description")
        summary = invoke_llm_with_reflection(request.job_description, request.config_file_path)

        return GenerateContentResponse(
            status="success", message="Content generated successfully", data=summary
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error generating content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating content: {str(e)}",
        )
