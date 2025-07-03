from fastapi import APIRouter, HTTPException, status
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_router = APIRouter(tags=["HR API Services"])

from base_requests import GenerateContentRequest, GenerateContentResponse
from test_run import generate_job_description


@api_router.post(
    "/generate",
    response_model=GenerateContentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid Request"},
        422: {"description": "Unprocessable Entity"},
    },
)
async def generate_content(request: GenerateContentRequest) -> GenerateContentResponse:
    try:
        logger.info("Generating content with provided job parameters...")

        # Convert request into dictionary if generate_job_description expects kwargs
        input_data = request.model_dump()

        # Generate the job description content
        job_description = generate_job_description(**input_data)

        return GenerateContentResponse(
            status="success",
            message="Content generated successfully",
            data=job_description,
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error generating content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating content: {str(e)}",
        )