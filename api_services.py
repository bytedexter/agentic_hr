from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
import logging
from base_requests import GenerateContentRequest, GenerateContentResponse
from test_run import generate_job_description
from docx import Document
import os
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_router = APIRouter(tags=["HR API Services"])


@api_router.post(
    "/generate",
    status_code=status.HTTP_200_OK,
    summary="Generate JD and return download link",
    responses={
        400: {"description": "Invalid Request"},
        422: {"description": "Unprocessable Entity"},
        500: {"description": "Internal Server Error"},
    },
)
async def generate_content(request: GenerateContentRequest):
    try:
        logger.info("Generating content with provided job parameters...")

        input_data = request.model_dump()
        job_description = generate_job_description(**input_data)

        if not job_description:
            raise HTTPException(status_code=500, detail="Failed to generate job description")

        # Save as .docx
        doc = Document()
        doc.add_heading('Job Description', 0)
        doc.add_paragraph(job_description)

        output_dir = "generated_docs"
        os.makedirs(output_dir, exist_ok=True)
        file_id = str(uuid.uuid4())
        output_path = os.path.join(output_dir, f"job_description_{file_id}.docx")
        doc.save(output_path)

        logger.info(f"Job description saved to {output_path}")

        download_url = f"/api/v1/download/{file_id}"  # Assuming prefix is /api/v1

        return {
            "status": "success",
            "message": "Content generated successfully",
            "data": {
                "job_description": job_description,
                "download_url": download_url
            }
        }

    except Exception as e:
        logger.error(f"Error generating content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating content: {str(e)}"
        )


@api_router.get(
    "/download/{file_id}",
    summary="Download the generated DOCX file",
    response_class=FileResponse
)
async def download_docx(file_id: str):
    output_dir = "generated_docs"
    file_path = os.path.join(output_dir, f"job_description_{file_id}.docx")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="job_description.docx"
    )
