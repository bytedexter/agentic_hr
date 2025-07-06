from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any# Request Classes


class GenerateContentRequest(BaseModel):
    """Request model for generating Job Description content."""

    job_description: str = Field(..., description="The full job description text to be scanned.")
    config_file_path: Optional[str] = Field(
        default="config/jd_output_format.json",
        description="Path to the JSON configuration file."
    )

    @field_validator("job_description")
    def validate_job_description(cls, value: str) -> str:
        """Ensure job_description is not empty."""
        if not value.strip():
            raise ValueError("job_description cannot be empty")
        return value.strip()


# Response Classes


class GenerateContentResponse(BaseModel):
    """Response model for job description generation."""

    status: str = Field(..., description="Status of the content generation")
    message: str = Field(..., description="Message about the content generation")
    data: Dict[str, Any] = Field(..., description="Generated content")

    @field_validator("data")
    def validate_data(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure data is not empty."""
        if not value:
            raise ValueError("Generated content cannot be empty")
        return value
