from pydantic import BaseModel, Field, field_validator

# Request Classes


class GenerateContentRequest(BaseModel):
    """Request model for generating content."""

    job_title: str = Field(..., description="The title or designation of the job position. (Mandatory)")
    location: str = Field(..., description="The location where the job is based. (Mandatory)")
    reporting_relationship: str = Field(..., description="The person or role to whom the candidate will report. (Mandatory)")
    function: str = Field(..., description="The department or functional area of the organization, such as Marketing, Sales, etc. (Mandatory)")
    role_overview: str = Field(..., description="A brief summary describing the purpose and scope of the role. (Mandatory)")
    key_responsibilities: str = Field(..., description="A list of primary duties and responsibilities for the role. (Mandatory)")
    qualifications: str = Field(..., description="The educational background or certifications required for the role. (Mandatory)")
    skills_and_competencies: str = Field(..., description="The required technical and soft skills, as well as core competencies needed for success in the role. (Mandatory)")
    our_company: str | None = Field(None, description="The company's website URL; system will fetch relevant company details. (Optional)")
    our_culture: str | None = Field(None, description="The company's website URL; system will fetch relevant information about the company's culture. (Optional)")
    local_llm: bool | None = Field(default=None, description="Indicates whether to use a local LLM for content generation. (Optional)")

    @field_validator("job_title", "location", "reporting_relationship", "function", "role_overview", "key_responsibilities", "qualifications", "skills_and_competencies")
    def validate_mandatory_fields(cls, value: str, info) -> str:
        """Ensure mandatory fields are not empty."""
        if not value or not value.strip():
            raise ValueError(f"{info.field_name.replace('_', ' ').capitalize()} cannot be empty")
        return value.strip()


# Response Classes


class GenerateContentResponse(BaseModel):
    """Response model for content generation."""

    status: str = Field(..., description="Status of the content generation")
    message: str = Field(..., description="Message about the content generation")
    data: str = Field(..., description="Generated content")

    @field_validator("data")
    def validate_data(cls, value: str) -> str:
        """Ensure data is not empty."""
        if not value.strip():
            raise ValueError("Generated content cannot be empty")
        return value.strip()