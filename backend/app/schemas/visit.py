"""Pydantic schemas for Visit API."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class VisitCreate(BaseModel):
    patient_id: Optional[int] = None
    health_id: Optional[str] = None
    visit_date: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=500)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    doctor_name: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    medicines: Optional[str] = None
    reactions: Optional[str] = None
    follow_up: Optional[str] = None


class VisitResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: Optional[int] = None
    visit_date: datetime
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    doctor_name: Optional[str] = None
    notes: Optional[str] = None
    medicines: Optional[str] = None
    reactions: Optional[str] = None
    follow_up: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
