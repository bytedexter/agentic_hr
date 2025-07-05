from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class JDScanRequest(BaseModel):
    job_description: str = Field(..., description="The full job description text to be scanned.")
    llm_reflection_count: Optional[int] = Field(default=3, description="How many self-reflection LLM calls to make.")
    config_file_path: Optional[str] = Field(default="config/config_output.xlsx", description="Path to the Excel rules.")

class JDScanResponse(BaseModel):
    result: Dict[str, Any] 
