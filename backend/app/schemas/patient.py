"""Pydantic schemas for Patient API."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PatientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=30)
    corridor: Optional[str] = Field(None, max_length=255)


class PatientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=30)
    corridor: Optional[str] = Field(None, max_length=255)


class PatientListItem(BaseModel):
    """Lightweight response for patient list view."""
    id: int
    health_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    visit_count: int = 0
    last_visit_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class PatientDetail(BaseModel):
    """Full patient detail response."""
    id: int
    health_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    corridor: Optional[str] = None
    created_at: Optional[datetime] = None
    visits: List["VisitResponse"] = []
    ai_analyses: List["AIAnalysisResponse"] = []

    class Config:
        from_attributes = True


class PatientResponse(BaseModel):
    id: int
    health_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    corridor: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Forward references resolved after all schemas are defined
from app.schemas.visit import VisitResponse
from app.schemas.ai import AIAnalysisResponse

PatientDetail.model_rebuild()
