from typing import Optional

from pydantic import BaseModel


class GenerateReportRequest(BaseModel):
    transcription: str
    templateText: str
    studyId: str
    patientId: str
    templateName: Optional[str] = "Freestyle Report"


class GenerateReportResponse(BaseModel):
    report: str


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
