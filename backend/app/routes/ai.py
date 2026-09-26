"""
AROG Routes - AI analysis and field visit endpoints.
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime

from app.database.database import get_db
from app.database.models import Patient, Visit, AIAnalysis, FieldVisit, User
from app.routes.auth import get_current_user
from app.schemas.ai import AIAnalysisStructured, AIAnalysisResponse, FieldVisitCreate, FieldVisitResponse
from app.services.ai_service import analyze_patient

router = APIRouter(tags=["AI & Field Visits"])


@router.post("/api/patients/{health_id}/analyze", response_model=AIAnalysisStructured)
async def analyze_patient_records(
    health_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI analysis of patient records.
    Collects visit history, sends to Gemini for summary + contradiction detection.
    Saves result in database. Returns structured analysis.
    
    The AI NEVER diagnoses. It only summarizes, detects missing info, and flags contradictions.
    """
    patient = db.query(Patient).filter(Patient.health_id == health_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient '{health_id}' not found.")

    visits = (
        db.query(Visit)
        .filter(Visit.patient_id == patient.id)
        .order_by(Visit.visit_date.asc())
        .all()
    )

    # Run AI analysis
    result = await analyze_patient(patient.name, patient.health_id, visits)

    # Save to database
    def safe_json(val):
        if isinstance(val, list):
            return json.dumps(val)
        return val or ""

    analysis = AIAnalysis(
        patient_id=patient.id,
        summary=result.get("summary", ""),
        past_treatments=safe_json(result.get("past_treatments", [])),
        medicines=safe_json(result.get("medicines", [])),
        reactions=safe_json(result.get("reactions", [])),
        missed_followups=safe_json(result.get("missed_followups", [])),
        trends=safe_json(result.get("trends", [])),
        missing_information=safe_json(result.get("missing_information", [])),
        contradictions=safe_json(result.get("contradictions", [])),
    )
    db.add(analysis)
    db.commit()

    return AIAnalysisStructured(**result)


@router.get("/api/ai")
def get_ai_status(current_user: User = Depends(get_current_user)):
    """Health check for AI service requiring doctor authentication."""
    return {"status": "ok", "service": "AROG AI Continuity Engine", "doctor": current_user.name}


# ---- Field Visit endpoints ----

@router.get("/api/field-visits", response_model=List[FieldVisitResponse])
def list_field_visits(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get field visits for the authenticated doctor only (Requirement 1 & 2).
    Merges visits at the same location and date into a single station record,
    incrementing the count and unifying patients treated.
    """
    field_visits = (
        db.query(FieldVisit)
        .filter(FieldVisit.doctor_id == current_user.id)
        .order_by(FieldVisit.visit_date.desc())
        .all()
    )

    # Group/merge field visits having the same location and calendar date for this doctor
    merged_groups = []
    seen_groups = {}  # key: (loc_normalized, date_str) -> index in merged_groups

    for fv in field_visits:
        loc_key = (fv.location_name or fv.location or "").strip().lower()
        v_dt = fv.visited_at or fv.visit_date
        date_key = v_dt.strftime("%Y-%m-%d") if v_dt else ""
        group_key = (loc_key, date_key)

        if group_key not in seen_groups:
            seen_groups[group_key] = len(merged_groups)
            merged_groups.append({
                "id": fv.id,
                "patient_id": fv.patient_id,
                "doctor_id": fv.doctor_id,
                "visit_id": fv.visit_id,
                "location": fv.location_name or fv.location,
                "location_name": fv.location_name or fv.location,
                "latitude": fv.latitude,
                "longitude": fv.longitude,
                "visit_date": fv.visit_date,
                "visited_at": fv.visited_at or fv.visit_date,
                "notes": fv.notes or "",
                "patients_seen": fv.patients_seen or 1,
                "new_patients": fv.new_patients or 0,
                "created_at": fv.created_at,
                "fv_records": [fv],
            })
        else:
            # Merge into existing group by incrementing count and combining notes
            idx = seen_groups[group_key]
            existing = merged_groups[idx]
            existing["patients_seen"] += (fv.patients_seen or 1)
            existing["new_patients"] += (fv.new_patients or 0)
            if fv.notes and fv.notes not in existing["notes"]:
                existing["notes"] = f"{existing['notes']} | {fv.notes}" if existing["notes"] else fv.notes
            if fv.latitude and not existing["latitude"]:
                existing["latitude"] = fv.latitude
            if fv.longitude and not existing["longitude"]:
                existing["longitude"] = fv.longitude
            existing["fv_records"].append(fv)

    results = []
    for g in merged_groups:
        loc_name = g["location"]
        # Find all visits by this specific doctor at this location
        matching_visits = (
            db.query(Visit)
            .filter(Visit.doctor_id == current_user.id, Visit.location == loc_name)
            .order_by(Visit.visit_date.desc())
            .all()
        )

        seen_pts = set()
        patients_treated_names = []
        patient_details_list = []

        for fv in g["fv_records"]:
            if fv.patient_id and fv.patient and fv.patient_id not in seen_pts:
                seen_pts.add(fv.patient_id)
                patients_treated_names.append(fv.patient.name)
                patient_details_list.append({
                    "name": fv.patient.name,
                    "health_id": fv.patient.health_id,
                    "visit_date": fv.visit_date,
                    "notes": fv.notes,
                })

        for v in matching_visits:
            if v.patient and v.patient_id not in seen_pts:
                seen_pts.add(v.patient_id)
                patients_treated_names.append(v.patient.name)
                patient_details_list.append({
                    "name": v.patient.name,
                    "health_id": v.patient.health_id,
                    "visit_date": v.visit_date,
                    "notes": v.notes,
                })

        patient_count = max(len(patients_treated_names), g["patients_seen"])
        visits_count = max(len(matching_visits), g["patients_seen"])

        results.append(
            FieldVisitResponse(
                id=g["id"],
                patient_id=g["patient_id"],
                doctor_id=g["doctor_id"],
                visit_id=g["visit_id"],
                location=g["location"],
                location_name=g["location_name"],
                latitude=g["latitude"],
                longitude=g["longitude"],
                visit_date=g["visit_date"],
                visited_at=g["visited_at"],
                notes=g["notes"],
                doctor=current_user.name,
                doctor_name=current_user.name,
                patients_seen=patient_count,
                new_patients=g["new_patients"],
                patient_count=patient_count,
                visits_count=visits_count,
                patients_treated=patients_treated_names,
                patient_details=patient_details_list,
                created_at=g["created_at"],
            )
        )

    return results[skip : skip + limit]


@router.post("/api/field-visits", response_model=FieldVisitResponse, status_code=201)
def create_field_visit(
    visit_data: FieldVisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a new field visit strictly tied to authenticated doctor. Merges if same location & date."""
    v_time = visit_data.visit_date or datetime.utcnow()
    v_day = v_time.date()
    loc = (visit_data.location or "").strip()

    existing = (
        db.query(FieldVisit)
        .filter(
            FieldVisit.doctor_id == current_user.id,
            func.lower(func.trim(FieldVisit.location)) == loc.lower(),
            func.date(FieldVisit.visit_date) == v_day,
        )
        .first()
    )

    if existing:
        existing.patients_seen = (existing.patients_seen or 1) + (visit_data.patients_seen or 1)
        existing.new_patients = (existing.new_patients or 0) + (visit_data.new_patients or 0)
        existing.visited_at = v_time
        if visit_data.latitude and not existing.latitude:
            existing.latitude = visit_data.latitude
        if visit_data.longitude and not existing.longitude:
            existing.longitude = visit_data.longitude
        if visit_data.notes:
            existing.notes = f"{existing.notes} | {visit_data.notes}" if existing.notes else visit_data.notes
        db.commit()
        db.refresh(existing)
        field_visit = existing
    else:
        field_visit = FieldVisit(
            patient_id=visit_data.patient_id,
            doctor_id=current_user.id,
            location=loc,
            location_name=loc,
            latitude=visit_data.latitude,
            longitude=visit_data.longitude,
            visit_date=v_time,
            visited_at=v_time,
            notes=visit_data.notes,
            doctor_name=current_user.name,
            patients_seen=visit_data.patients_seen or 1,
            new_patients=visit_data.new_patients or 0,
        )
        db.add(field_visit)
        db.commit()
        db.refresh(field_visit)

    return FieldVisitResponse(
        id=field_visit.id,
        patient_id=field_visit.patient_id,
        doctor_id=field_visit.doctor_id,
        visit_id=field_visit.visit_id,
        location=field_visit.location,
        location_name=field_visit.location_name or field_visit.location,
        latitude=field_visit.latitude,
        longitude=field_visit.longitude,
        visit_date=field_visit.visit_date,
        visited_at=field_visit.visited_at or field_visit.visit_date,
        notes=field_visit.notes,
        doctor=current_user.name,
        doctor_name=current_user.name,
        patients_seen=field_visit.patients_seen,
        new_patients=field_visit.new_patients,
        patient_count=field_visit.patients_seen,
        visits_count=1,
        patients_treated=[],
        patient_details=[],
        created_at=field_visit.created_at,
    )

