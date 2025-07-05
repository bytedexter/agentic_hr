from fastapi import APIRouter, HTTPException
from app.models.schemas import JDScanRequest, JDScanResponse
from app.services.jd_scanner import scan_job_description

router = APIRouter(prefix="/jd", tags=["Job Description Scanner"])

@router.post("/scan", response_model=JDScanResponse)
async def scan_jd(request: JDScanRequest):
    try:
        result = scan_job_description(request.job_description, request.llm_reflection_count, request.config_file_path)
        return JDScanResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
