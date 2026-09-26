"""
AROG Routes - Doctor-specific Archival Dossier & PDF Generation (Requirement 8).
Generates an authenticated doctor's clinical archive containing ONLY their visits,
patients treated by them, and their field stations.
"""
import io
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.database.database import get_db
from app.database.models import User, Patient, Visit, FieldVisit
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/archive", tags=["Archive"])


@router.get("")
def get_doctor_archive_json(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve structured JSON archive strictly scoped to the authenticated doctor.
    Never includes records or field visits from other clinicians.
    """
    # Visits by this doctor only
    visits = (
        db.query(Visit)
        .filter(Visit.doctor_id == current_user.id)
        .order_by(Visit.visit_date.desc())
        .all()
    )

    # Distinct patients treated by this doctor
    patient_ids = list({v.patient_id for v in visits if v.patient_id})
    patients = (
        db.query(Patient)
        .filter(Patient.id.in_(patient_ids))
        .all() if patient_ids else []
    )

    # Field visits by this doctor only
    field_visits = (
        db.query(FieldVisit)
        .filter(FieldVisit.doctor_id == current_user.id)
        .order_by(FieldVisit.visit_date.desc())
        .all()
    )

    return {
        "doctor": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "role": "Travelling Clinician",
        },
        "patients_treated_count": len(patients),
        "total_visits_count": len(visits),
        "total_field_locations_count": len(field_visits),
        "patients": [
            {
                "id": p.id,
                "health_id": p.health_id,
                "name": p.name,
                "age": p.age,
                "gender": p.gender,
                "corridor": p.corridor,
            }
            for p in patients
        ],
        "visits": [
            {
                "id": v.id,
                "patient_id": v.patient_id,
                "patient_name": v.patient.name if v.patient else "Unknown",
                "patient_health_id": v.patient.health_id if v.patient else "N/A",
                "date": v.visit_date.isoformat(),
                "location": v.location,
                "notes": v.notes,
                "medicines": v.medicines,
                "reactions": v.reactions,
                "follow_up": v.follow_up,
            }
            for v in visits
        ],
        "field_visits": [
            {
                "id": f.id,
                "location": f.location,
                "latitude": f.latitude,
                "longitude": f.longitude,
                "date": f.visit_date.isoformat(),
                "notes": f.notes,
                "patients_seen": f.patients_seen,
            }
            for f in field_visits
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/pdf")
def download_doctor_archive_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate and download doctor-specific PDF archive.
    Backend query enforces that ONLY records belonging to current_user.id are included.
    """
    # 1. Fetch doctor visits
    visits = (
        db.query(Visit)
        .filter(Visit.doctor_id == current_user.id)
        .order_by(Visit.visit_date.desc())
        .all()
    )

    patient_ids = list({v.patient_id for v in visits if v.patient_id})
    patients = (
        db.query(Patient)
        .filter(Patient.id.in_(patient_ids))
        .all() if patient_ids else []
    )

    field_visits = (
        db.query(FieldVisit)
        .filter(FieldVisit.doctor_id == current_user.id)
        .order_by(FieldVisit.visit_date.desc())
        .all()
    )

    # 2. Build PDF Document
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Color Palette: AROG Terracotta Aesthetic
    c_primary = colors.HexColor("#703423")
    c_secondary = colors.HexColor("#545f72")
    c_bg_light = colors.HexColor("#fff8f5")
    c_surface_container = colors.HexColor("#f5ece7")
    c_dark = colors.HexColor("#1e1b18")

    title_style = ParagraphStyle(
        "ArogTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=c_primary,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ArogSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=c_secondary,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "ArogSectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ArogBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=c_dark,
    )
    meta_style = ParagraphStyle(
        "ArogMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=c_secondary,
    )

    story = []

    # Header
    story.append(Paragraph("AROG • CONTINUITY CLINICAL ARCHIVE", title_style))
    story.append(
        Paragraph(
            f"Archival Dispatch Ledger for <b>{current_user.name}</b> • {current_user.email}<br/>"
            f"Generated on {datetime.utcnow().strftime('%d %B %Y, %H:%M UTC')} • Official Medical Continuity Record",
            subtitle_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceBefore=4, spaceAfter=12))

    # Clinician & Scope Summary Box
    summary_data = [
        [
            Paragraph("<b>Clinician Profile</b>", body_style),
            Paragraph(f"Dr. {current_user.name}", body_style),
            Paragraph("<b>Total Treated Patients</b>", body_style),
            Paragraph(str(len(patients)), body_style),
        ],
        [
            Paragraph("<b>Clinical Role</b>", body_style),
            Paragraph("Travelling Clinician", body_style),
            Paragraph("<b>Visits Recorded</b>", body_style),
            Paragraph(str(len(visits)), body_style),
        ],
        [
            Paragraph("<b>Archive Filter</b>", body_style),
            Paragraph(f"Clinician ID #{current_user.id} (Strict Enforced)", body_style),
            Paragraph("<b>Field Stations Visited</b>", body_style),
            Paragraph(str(len(field_visits)), body_style),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[110, 150, 130, 140])
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), c_surface_container),
            ("TEXTCOLOR", (0, 0), (-1, -1), c_dark),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.5, c_secondary),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9c2bc")),
        ])
    )
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # Section 1: Patients Treated by This Doctor
    story.append(Paragraph(f"1. Patients Treated by Dr. {current_user.name}", heading_style))
    if patients:
        pt_table_data = [
            [
                Paragraph("<b>Health ID</b>", body_style),
                Paragraph("<b>Patient Name</b>", body_style),
                Paragraph("<b>Age / Gender</b>", body_style),
                Paragraph("<b>Corridor</b>", body_style),
            ]
        ]
        for p in patients:
            age_gender = f"{p.age or 'N/A'}y • {p.gender or 'Unspecified'}"
            pt_table_data.append([
                Paragraph(f"<b>{p.health_id}</b>", body_style),
                Paragraph(p.name, body_style),
                Paragraph(age_gender, body_style),
                Paragraph(p.corridor or "Universal", body_style),
            ])
        pt_table = Table(pt_table_data, colWidths=[100, 140, 120, 170])
        pt_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), c_surface_container),
                ("PADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9c2bc")),
            ])
        )
        story.append(pt_table)
    else:
        story.append(Paragraph("<i>No patients recorded for this clinician.</i>", meta_style))

    story.append(Spacer(1, 10))

    # Section 2: Clinical Encounters / Visits
    story.append(Paragraph(f"2. Clinical Visits Performed by Dr. {current_user.name}", heading_style))
    if visits:
        v_table_data = [
            [
                Paragraph("<b>Date / Location</b>", body_style),
                Paragraph("<b>Patient</b>", body_style),
                Paragraph("<b>Clinical Notes & Prescriptions</b>", body_style),
            ]
        ]
        for v in visits:
            v_date = v.visit_date.strftime("%d %b %Y, %H:%M") if hasattr(v.visit_date, "strftime") else str(v.visit_date)[:16]
            pt_name = v.patient.name if v.patient else "Patient"
            pt_hid = v.patient.health_id if v.patient else "N/A"

            date_loc = f"<b>{v_date}</b><br/>{v.location or 'Outpost Station'}"
            pt_info = f"<b>{pt_name}</b><br/>{pt_hid}"

            notes_content = f"{v.notes or 'Routine consultation.'}"
            if v.medicines:
                notes_content += f"<br/><b>Rx:</b> {v.medicines}"
            if v.reactions:
                notes_content += f"<br/><b>Reactions:</b> {v.reactions}"
            if v.follow_up:
                notes_content += f"<br/><b>Follow-up:</b> {v.follow_up}"

            v_table_data.append([
                Paragraph(date_loc, body_style),
                Paragraph(pt_info, body_style),
                Paragraph(notes_content, body_style),
            ])

        v_table = Table(v_table_data, colWidths=[140, 110, 280])
        v_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), c_surface_container),
                ("PADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9c2bc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )
        story.append(v_table)
    else:
        story.append(Paragraph("<i>No visits recorded yet for this clinician.</i>", meta_style))

    story.append(Spacer(1, 10))

    # Section 3: Field Outreach Stations
    story.append(Paragraph(f"3. Field Visits & Stations Logged by Dr. {current_user.name}", heading_style))
    if field_visits:
        fv_table_data = [
            [
                Paragraph("<b>Date</b>", body_style),
                Paragraph("<b>Station Location</b>", body_style),
                Paragraph("<b>Coordinates</b>", body_style),
                Paragraph("<b>Patients Seen</b>", body_style),
            ]
        ]
        for f in field_visits:
            f_date = f.visit_date.strftime("%d %b %Y") if hasattr(f.visit_date, "strftime") else str(f.visit_date)[:10]
            coords = f"{f.latitude:.4f}°N, {f.longitude:.4f}°E" if f.latitude and f.longitude else "GPS Unrecorded"
            fv_table_data.append([
                Paragraph(f_date, body_style),
                Paragraph(f.location, body_style),
                Paragraph(coords, body_style),
                Paragraph(str(f.patients_seen or 1), body_style),
            ])

        fv_table = Table(fv_table_data, colWidths=[80, 200, 150, 100])
        fv_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), c_surface_container),
                ("PADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9c2bc")),
            ])
        )
        story.append(fv_table)
    else:
        story.append(Paragraph("<i>No field outreach stations logged yet for this clinician.</i>", meta_style))

    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=0.5, color=c_secondary, spaceBefore=4, spaceAfter=8))
    story.append(
        Paragraph(
            "<b>AROG Healthcare Continuity</b> • Thoughtfully Archived • © 2026 AROG<br/>"
            "This document is an authenticated clinical extract. Certified under travelling physician continuity protocols.",
            meta_style,
        )
    )

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    clean_filename = f"AROG_Archive_{current_user.name.replace(' ', '_').replace('.', '')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{clean_filename}"'},
    )
