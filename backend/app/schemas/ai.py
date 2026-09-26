"""Pydantic schemas for AI Analysis and Field Visits."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AIAnalysisResponse(BaseModel):
    id: int
    patient_id: int
    summary: Optional[str] = None
    past_treatments: Optional[str] = None
    medicines: Optional[str] = None
    reactions: Optional[str] = None
    missed_followups: Optional[str] = None
    trends: Optional[str] = None
    missing_information: Optional[str] = None
    contradictions: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AIAnalysisStructured(BaseModel):
    """Structured AI analysis result returned to the frontend."""
    summary: str = ""
    past_treatments: List[str] = []
    medicines: List[str] = []
    reactions: List[str] = []
    missed_followups: List[str] = []
    trends: List[str] = []
    missing_information: List[str] = []
    contradictions: List[str] = []


class FieldVisitCreate(BaseModel):
    patient_id: Optional[int] = None
    location: str = Field(..., min_length=1, max_length=500)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    visit_date: Optional[datetime] = None
    notes: Optional[str] = None
    doctor_name: Optional[str] = Field(None, max_length=255)
    patients_seen: Optional[int] = Field(None, ge=0)
    new_patients: Optional[int] = Field(None, ge=0)


class FieldVisitPatientDetail(BaseModel):
    name: str
    health_id: Optional[str] = None
    visit_date: Optional[datetime] = None
    notes: Optional[str] = None


class FieldVisitResponse(BaseModel):
    id: int
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    visit_id: Optional[int] = None
    location: str
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    visit_date: datetime
    visited_at: Optional[datetime] = None
    notes: Optional[str] = None
    doctor: Optional[str] = None
    doctor_name: Optional[str] = None
    patients_seen: Optional[int] = None
    new_patients: Optional[int] = None
    patient_count: Optional[int] = None
    visits_count: Optional[int] = 1
    patients_treated: List[str] = []
    patient_details: List[FieldVisitPatientDetail] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OCRStructuredData(BaseModel):
    patient_name: Optional[str] = None
    date: Optional[str] = None
    medicine: Optional[str] = None
    dosage: Optional[str] = None
    notes: Optional[str] = None
    follow_up: Optional[str] = None


class OCRResponse(BaseModel):
    """Response from OCR endpoint."""
    extracted_text: str
    structured_data: Optional[OCRStructuredData] = None
    confidence: Optional[float] = None
    message: str = "Text extracted successfully. Please review and edit before saving."

