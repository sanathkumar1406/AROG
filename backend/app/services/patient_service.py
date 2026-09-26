"""
AROG Patient Service - Business logic for patient operations.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import Patient, Visit
from app.schemas.patient import PatientCreate, PatientUpdate
from typing import Optional, List


def get_patients(db: Session, search: Optional[str] = None, skip: int = 0, limit: int = 10):
    """
    Get patients list.
    Default: Returns ONLY RECENT PATIENTS, ordered by most recent clinical visit/activity first.
    Search: Queries across name, Health ID, phone number, or corridor.
    """
    latest_visit_subq = (
        db.query(
            Visit.patient_id.label("v_patient_id"),
            func.max(Visit.visit_date).label("latest_visit")
        )
        .group_by(Visit.patient_id)
        .subquery()
    )

    query = db.query(Patient).outerjoin(latest_visit_subq, Patient.id == latest_visit_subq.c.v_patient_id)

    if search and search.strip():
        search_term = f"%{search.strip()}%"
        query = query.filter(
            (Patient.name.ilike(search_term)) |
            (Patient.health_id.ilike(search_term)) |
            (Patient.phone.ilike(search_term)) |
            (Patient.corridor.ilike(search_term))
        )
        patients = (
            query.order_by(
                func.coalesce(latest_visit_subq.c.latest_visit, Patient.created_at).desc()
            )
            .offset(skip)
            .limit(limit if limit > 10 else 50)
            .all()
        )
    else:
        # Default: Only recent patients ordered by latest visit date descending
        patients = (
            query.order_by(
                func.coalesce(latest_visit_subq.c.latest_visit, Patient.created_at).desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    # Enrich with visit count and last visit date
    result = []
    for p in patients:
        visit_info = db.query(
            func.count(Visit.id),
            func.max(Visit.visit_date)
        ).filter(Visit.patient_id == p.id).first()

        result.append({
            "id": p.id,
            "health_id": p.health_id,
            "name": p.name,
            "age": p.age,
            "gender": p.gender,
            "visit_count": visit_info[0] if visit_info else 0,
            "last_visit_date": visit_info[1] if visit_info else None,
        })

    return result


def get_patient_by_health_id(db: Session, health_id: str) -> Optional[Patient]:
    """Get a single patient by health_id."""
    return db.query(Patient).filter(Patient.health_id == health_id).first()


def create_patient(db: Session, patient_data: PatientCreate) -> Patient:
    """Create a new patient with auto-generated Health ID."""
    patient = Patient(
        name=patient_data.name,
        age=patient_data.age,
        gender=patient_data.gender,
        phone=patient_data.phone,
        corridor=patient_data.corridor,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def update_patient(db: Session, health_id: str, patient_data: PatientUpdate) -> Optional[Patient]:
    """Update patient info."""
    patient = get_patient_by_health_id(db, health_id)
    if not patient:
        return None

    update_data = patient_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(patient, key, value)

    db.commit()
    db.refresh(patient)
    return patient
