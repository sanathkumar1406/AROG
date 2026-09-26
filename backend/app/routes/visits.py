"""
AROG Routes - Visit endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime

from app.database.database import get_db
from app.database.models import Patient, Visit, FieldVisit, User
from app.routes.auth import get_current_user
from app.schemas.visit import VisitCreate, VisitResponse

from typing import List, Optional

router = APIRouter(tags=["Visits"])


@router.get("/api/visits", response_model=List[VisitResponse])
def list_visits_global(
    health_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get visits list.
    If health_id is provided, returns visits for that patient.
    Otherwise, returns visits performed by the authenticated doctor.
    """
    if health_id:
        patient = db.query(Patient).filter(Patient.health_id == health_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient '{health_id}' not found.")
        return (
            db.query(Visit)
            .filter(Visit.patient_id == patient.id)
            .order_by(Visit.visit_date.desc())
            .all()
        )
    return (
        db.query(Visit)
        .filter(Visit.doctor_id == current_user.id)
        .order_by(Visit.visit_date.desc())
        .all()
    )


@router.get("/api/patients/{health_id}/visits", response_model=List[VisitResponse])
def list_visits(
    health_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all visits for a patient (chronological continuity)."""
    patient = db.query(Patient).filter(Patient.health_id == health_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient '{health_id}' not found.")

    visits = (
        db.query(Visit)
        .filter(Visit.patient_id == patient.id)
        .order_by(Visit.visit_date.desc())
        .all()
    )
    return visits


@router.post("/api/visits", response_model=VisitResponse, status_code=201)
def create_visit_direct(
    visit_data: VisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Direct endpoint to create a visit. Resolves patient via health_id or patient_id.
    """
    patient = None
    if visit_data.health_id:
        patient = db.query(Patient).filter(Patient.health_id == visit_data.health_id).first()
    elif visit_data.patient_id:
        patient = db.query(Patient).filter(Patient.id == visit_data.patient_id).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Valid patient_id or health_id required to record visit.")

    return add_visit(patient.health_id, visit_data, db, current_user)


@router.post("/api/patients/{health_id}/visits", response_model=VisitResponse, status_code=201)
def add_visit(
    health_id: str,
    visit_data: VisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add a new visit record for a patient.
    Doctor name and ID are strictly retrieved from the authenticated user profile.
    Automatically records field visit coordinates and updates the field visit ledger.
    """
    patient = db.query(Patient).filter(Patient.health_id == health_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient '{health_id}' not found.")

    visit_time = visit_data.visit_date or datetime.utcnow()
    loc = (visit_data.location or "Regional Care Outpost").strip()

    visit = Visit(
        patient_id=patient.id,
        doctor_id=current_user.id,
        doctor_name=current_user.name,  # Strictly from authenticated profile
        visit_date=visit_time,
        location=loc,
        latitude=visit_data.latitude,
        longitude=visit_data.longitude,
        notes=visit_data.notes,
        medicines=visit_data.medicines,
        reactions=visit_data.reactions,
        follow_up=visit_data.follow_up,
    )
    db.add(visit)
    db.flush()  # Obtain visit.id

    # Sync to field_visits: merge into existing record if location and date match for this doctor
    visit_day = visit_time.date()
    existing_field_visit = (
        db.query(FieldVisit)
        .filter(
            FieldVisit.doctor_id == current_user.id,
            func.lower(func.trim(FieldVisit.location)) == loc.lower(),
            func.date(FieldVisit.visit_date) == visit_day,
        )
        .first()
    )

    if existing_field_visit:
        # Merge by incrementing patients_seen and updating timestamp
        existing_field_visit.patients_seen = (existing_field_visit.patients_seen or 1) + 1
        existing_field_visit.visited_at = visit_time
        if visit_data.latitude is not None and visit_data.longitude is not None:
            existing_field_visit.latitude = visit_data.latitude
            existing_field_visit.longitude = visit_data.longitude

        entry_note = f"Patient {patient.name} ({patient.health_id}): {visit_data.notes or 'Consultation'}"
        if existing_field_visit.notes:
            if patient.name not in existing_field_visit.notes:
                existing_field_visit.notes = f"{existing_field_visit.notes} | {entry_note}"
        else:
            existing_field_visit.notes = entry_note
    else:
        field_log = FieldVisit(
            patient_id=patient.id,
            doctor_id=current_user.id,
            visit_id=visit.id,
            location=loc,
            location_name=loc,
            latitude=visit_data.latitude,
            longitude=visit_data.longitude,
            visit_date=visit_time,
            visited_at=visit_time,
            notes=f"Patient {patient.name} ({patient.health_id}): {visit_data.notes or 'Routine consultation'}",
            doctor_name=current_user.name,
            patients_seen=1,
            new_patients=0,
        )
        db.add(field_log)

    db.commit()
    db.refresh(visit)
    return visit


