"""
AROG Backend - Main FastAPI application.
AI-Powered Continuity of Care Platform.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load backend environment variables from .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.database.database import engine, SessionLocal, Base
from app.database.models import Patient, Visit, AIAnalysis, FieldVisit, User

from app.routes import patients, visits, ocr, ai, auth, archive
from app.routes.auth import get_current_user, UserProfileResponse
from fastapi import Depends

# Create all tables on startup
Base.metadata.create_all(bind=engine)

# Create uploads directory
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = FastAPI(
    title="AROG - Continuity of Care API",
    description="AI-Powered platform for travelling doctors. Manages patient Health IDs, visit records, OCR document scanning, and AI-powered analysis.",
    version="1.0.0",
)

# CORS - allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For hackathon MVP; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

from fastapi.responses import RedirectResponse

# Register routes
app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(visits.router)
app.include_router(ocr.router)
app.include_router(ai.router)
app.include_router(archive.router)


@app.get("/api/profile", response_model=UserProfileResponse, tags=["Authentication"])
def get_user_profile(current_user: User = Depends(get_current_user)):
    """Retrieve authenticated doctor profile (Requirement 10)."""
    return UserProfileResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role="Travelling Clinician",
        created_at=current_user.created_at,
    )


@app.get("/api/config/maps", tags=["Configuration"])
def get_maps_config(current_user: User = Depends(get_current_user)):
    """
    Safely provide browser-restricted Google Maps API key from backend environment (Requirement 4).
    Enforces authentication so keys are never exposed publicly.
    """
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    return {
        "google_maps_api_key": maps_key if maps_key != "YOUR_KEY" and not maps_key.startswith("your_") else "",
    }



@app.get("/", include_in_schema=False)
@app.get("/home", include_in_schema=False)
def root():
    """Redirect root to the AROG Home landing page."""
    return RedirectResponse(url="/frontend/arog_healthcare_continuity_home/code.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return RedirectResponse(url="/frontend/arog_sign_in_clinical_portal/code.html")


@app.get("/patients", include_in_schema=False)
@app.get("/health-id", include_in_schema=False)
@app.get("/care-check", include_in_schema=False)
def patients_page():
    return RedirectResponse(url="/frontend/arog_patients_continuity_records/code.html")


@app.get("/timeline", include_in_schema=False)
@app.get("/field-visits", include_in_schema=False)
def field_visits_page():
    return RedirectResponse(url="/frontend/arog_field_visits_where_care_happened/code.html")


@app.get("/health", tags=["Health"])
def health_check():
    """Basic health check."""
    return {"status": "ok"}


@app.get("/api/health/db", tags=["Health"])
def db_health_check():
    """Check database connectivity."""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "disconnected", "detail": str(e)}
