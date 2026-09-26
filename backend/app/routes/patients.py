"""
AROG Routes - Patient endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database.database import get_db
from app.database.models import Patient, User
from app.routes.auth import get_current_user
from app.schemas.patient import (
    PatientCreate, PatientUpdate, PatientListItem, PatientDetail, PatientResponse
)
from app.schemas.visit import VisitResponse
from app.schemas.ai import AIAnalysisResponse
from app.services.patient_service import (
    get_patients, get_patient_by_health_id, create_patient, update_patient
)

router = APIRouter(prefix="/api/patients", tags=["Patients"])


@router.get("", response_model=List[PatientListItem])
def list_patients(
    search: Optional[str] = Query(None, description="Search by name, Health ID, or phone"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recent patients list (or search all patients) for authenticated clinicians."""
    return get_patients(db, search=search, skip=skip, limit=limit)


@router.post("", response_model=PatientResponse, status_code=201)
def register_patient(
    patient_data: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a new patient. Backend generates the Health ID."""
    patient = create_patient(db, patient_data)
    return patient


@router.get("/{health_id}", response_model=PatientDetail)
def get_patient(
    health_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full patient details including visits and AI analysis."""
    patient = get_patient_by_health_id(db, health_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient with Health ID '{health_id}' not found.")

    return PatientDetail(
        id=patient.id,
        health_id=patient.health_id,
        name=patient.name,
        age=patient.age,
        gender=patient.gender,
        phone=patient.phone,
        corridor=patient.corridor,
        created_at=patient.created_at,
        visits=[VisitResponse.model_validate(v) for v in patient.visits],
        ai_analyses=[AIAnalysisResponse.model_validate(a) for a in patient.ai_analyses],
    )


@router.put("/{health_id}", response_model=PatientResponse)
def update_patient_info(
    health_id: str,
    patient_data: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update patient information."""
    patient = update_patient(db, health_id, patient_data)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient with Health ID '{health_id}' not found.")
    return patient

