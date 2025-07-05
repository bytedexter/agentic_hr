from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class JDScanRequest(BaseModel):
    job_description: str = Field(..., description="The full job description text to be scanned.")
    llm_reflection_count: Optional[int] = Field(default=3, description="How many self-reflection LLM calls to make.")
    config_file_path: Optional[str] = Field(
        default="app/config/jd_output_format.json",
        description="Path to the JSON configuration file."
    )
class JDScanResponse(BaseModel):
    result: Dict[str, Any] 
