"""
AROG Backend - SQLAlchemy ORM models.
Tables: users, patients, visits, ai_analyses, field_visits
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from app.database.database import Base


def generate_health_id():
    """Generate a unique Health ID like AROG-7F29A1."""
    return "AROG-" + uuid.uuid4().hex[:6].upper()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    health_id = Column(String(20), unique=True, nullable=False, default=generate_health_id)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    phone = Column(String(30), nullable=True)
    corridor = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    visits = relationship("Visit", back_populates="patient", order_by="desc(Visit.visit_date)")
    ai_analyses = relationship("AIAnalysis", back_populates="patient", order_by="desc(AIAnalysis.created_at)")

    __table_args__ = (
        Index("ix_patients_health_id", "health_id"),
    )


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    visit_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    location = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    doctor_name = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    medicines = Column(Text, nullable=True)
    reactions = Column(Text, nullable=True)
    follow_up = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="visits")
    doctor = relationship("User", backref="visits")

    __table_args__ = (
        Index("ix_visits_patient_id", "patient_id"),
        Index("ix_visits_visit_date", "visit_date"),
        Index("ix_visits_doctor_id", "doctor_id"),
    )


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    summary = Column(Text, nullable=True)
    past_treatments = Column(Text, nullable=True)
    medicines = Column(Text, nullable=True)
    reactions = Column(Text, nullable=True)
    missed_followups = Column(Text, nullable=True)
    trends = Column(Text, nullable=True)
    missing_information = Column(Text, nullable=True)
    contradictions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="ai_analyses")


class FieldVisit(Base):
    __tablename__ = "field_visits"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True)
    doctor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    visit_id = Column(Integer, ForeignKey("visits.id", ondelete="SET NULL"), nullable=True)
    location = Column(String(500), nullable=False)
    location_name = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    visit_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    visited_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    doctor_name = Column(String(255), nullable=True)
    patients_seen = Column(Integer, nullable=True, default=1)
    new_patients = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", backref="field_visits")
    doctor = relationship("User", backref="field_visits")
    visit = relationship("Visit", backref="field_visits")

    def __init__(self, **kwargs):
        if "location" in kwargs and "location_name" not in kwargs:
            kwargs["location_name"] = kwargs["location"]
        elif "location_name" in kwargs and "location" not in kwargs:
            kwargs["location"] = kwargs["location_name"]

        if "visit_date" in kwargs and "visited_at" not in kwargs:
            kwargs["visited_at"] = kwargs["visit_date"]
        elif "visited_at" in kwargs and "visit_date" not in kwargs:
            kwargs["visit_date"] = kwargs["visited_at"]

        super().__init__(**kwargs)

    __table_args__ = (
        Index("ix_field_visits_visit_date", "visit_date"),
        Index("ix_field_visits_patient_id", "patient_id"),
        Index("ix_field_visits_doctor_id", "doctor_id"),
        Index("ix_field_visits_visit_id", "visit_id"),
    )

