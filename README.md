# AROG: Healthcare Continuity Platform for Traveling Clinicians

AROG is an AI-powered healthcare continuity platform designed for mobile clinics, traveling doctors, and regional outreach programs. It ensures that medical records, pharmacotherapy timelines, and clinical history remain continuous and accessible across disparate visiting posts without relying on centralized hospital infrastructure.

---

## Table of Contents

1. Overview and Core Philosophy
2. System Architecture
3. Technology Stack
4. Key Capabilities and Clinical Workflows
5. Database Design and Schema
6. API Specification
7. Local Development Setup
8. Production Deployment Guide
9. Verification and Testing
10. Security and Data Governance

---

## 1. Overview and Core Philosophy

In rural outreach healthcare, patient treatment is often fragmented. Patients visit mobile camps or outpost stations operated by different clinicians across different dates. Without unified tracking:
- Prior prescriptions and discontinued medications are lost.
- Drug allergies and adverse reactions are not communicated across visiting teams.
- Duplication of treatments and conflicting drug regimens occur.

AROG solves this through a shared-patient, authenticated-doctor continuity model:
- **Shared Patient Continuity:** Patients hold a persistent Health ID (e.g., `AROG-HC2048`) that any authenticated visiting clinician can look up to access full clinical history.
- **Strict Doctor Attribution:** Clinicians authenticate with dedicated credentials. Outpost field visits, map stations, clinical signatures, and downloaded dossiers belong strictly to the authenticated clinician.
- **Non-Diagnostic Clinical Synthesis:** Machine intelligence synthesizes multi-visit records to highlight missing diagnostic documentation, dosage omissions, discontinued therapies, and cross-encounter contradictions without ever guessing, diagnosing, or prescribing.

---

## 2. System Architecture

The application operates as a unified monolithic service where FastAPI handles API routing, authentication, business logic, machine learning inference, and static frontend delivery.

```
                           +----------------------------------------+
                           |           Client Web Browser           |
                           |   (Desktop / Tablet / Mobile View)     |
                           +-------------------+--------------------+
                                               |
                          HTTPS / REST API / Static Assets
                                               |
                           +-------------------v--------------------+
                           |             FastAPI Core               |
                           |   (Python 3.10 / Uvicorn Server)       |
                           +--------+--------------------+----------+
                                    |                    |
            +-----------------------+                    +-----------------------+
            |                                                                    |
+-----------v-----------+                                            +-----------v-----------+
|  PostgreSQL Database  |                                            |   TrOCR ONNX Runtime  |
|  - Users (Doctors)    |                                            |  - Encoder (384x384)  |
|  - Patients           |                                            |  - Decoder (KV-Cache) |
|  - Clinical Visits    |                                            |  - Structured Parser  |
|  - Field Stations     |                                            +-----------------------+
|  - AI Syntheses       |                                                        |
+-----------------------+                                            +-----------v-----------+
            |                                                        |   Google Gemini API   |
+-----------v-----------+                                            |  - Continuity Summary |
| ReportLab PDF Engine  |                                            |  - Conflict Detection |
| - Doctor Dossiers     |                                            |  - Missing Info Check |
+-----------------------+                                            +-----------------------+
```

---

## 3. Technology Stack

### Backend
- **Language:** Python 3.10+
- **Web Framework:** FastAPI (ASGI)
- **Server:** Uvicorn
- **ORM & Data Access:** SQLAlchemy, psycopg2-binary
- **Authentication:** JWT (JSON Web Tokens), OAuth2 password bearer flow with bcrypt hashing
- **PDF Generation:** ReportLab 5.0.1+
- **Environment Management:** python-dotenv

### Database
- **Engine:** PostgreSQL 14+
- **Relational Integrity:** Foreign keys across patients, clinicians, visits, and field stations
- **Automatic Initialization:** SQLAlchemy metadata reflection on service startup

### Machine Learning and AI
- **Handwritten Document OCR:** Microsoft TrOCR Float ONNX model (encoder + autoregressive decoder) executed locally via `onnxruntime` (no third-party cloud data transmission for OCR images)
- **Clinical Continuity Synthesis:** Google Gemini Interactions API (`gemini-3.8-flash`) with automated fallback to an internal deterministic clinical rules engine during network degradation

### Frontend
- **Structure and Logic:** Semantic HTML5, Vanilla JavaScript ES6+
- **Styling:** Vanilla CSS, Tailwind CSS utility system, custom warm terracotta aesthetic
- **Typography:** Playfair Display, Plus Jakarta Sans, Caveat (hand-annotated feel)
- **Cartography:** Google Maps JavaScript SDK with custom warm vintage styling and automated Leaflet (OpenStreetMap) fallback

---

## 4. Key Capabilities and Clinical Workflows

### 4.1 Shared Patient Directory and Zero-Data-Flash Security
- Unauthenticated requests to `/patients` never render clinical records. The interface enforces a neutral loading state (`Checking authentication...`) and redirects directly to the login portal.
- All patient queries require valid Bearer token authorization.

### 4.2 Doctor-Specific Field Visits and Interactive Cartography
- When an authenticated clinician views the Field Visits ledger, the backend query filters records strictly by `current_authenticated_doctor_id`. Doctor A never views Doctor B's field locations.
- Map markers render only stations visited by the active clinician.
- Clicking a station displays a compact popup with location name, patient count, last visit date, and attending clinician.
- The details panel reveals only patients treated by the active clinician at that station.

### 4.3 Automatic Field Station Consolidation
- When a clinician records an encounter with geolocation (`latitude` and `longitude`), the backend verifies if a field station already exists for that clinician, location name, and calendar date.
- If a record exists for the same location and date, it merges the record into a single outpost pin, increments the patient count, and unifies encounter notes rather than generating duplicate overlapping map points.

### 4.4 TrOCR Prescription Scanner and Live Camera Capture
- Clinicians can ingest legacy physical records via file upload or integrated device camera (`navigator.mediaDevices.getUserMedia`).
- The OCR pipeline extracts raw text and executes structured regex parsing for patient name, encounter date, prescribed medication, dosage, and review instructions.
- Extracted values populate an editable staging container. No data is committed to PostgreSQL until the clinician explicitly confirms and submits the form.

### 4.5 Guardrailed Clinical Continuity Synthesis
- The AI summary never triggers automatically upon opening a patient. Clinicians initiate synthesis explicitly via the "AI Continuity Summary" action.
- The request transmits only the records of the active patient to the backend.
- Strict clinical prompts enforce:
  - Absolute prohibition against diagnosing, prescribing, or recommending treatments.
  - Omitted dosage fields are reported explicitly as `"Dosage not recorded."`
  - Discontinued medications without a recorded reason are flagged as `"Reason for stopping not recorded. Please verify with patient."`
  - Cross-encounter discrepancies (e.g. conflicting allergy documentation between visits) are flagged as clinical contradictions for human review.

### 4.6 Scoped Clinician Archive Export
- Clinicians can generate a structured clinical ledger and downloadable PDF dossier via `/api/archive/pdf`.
- Dossiers include clinician credentials, treated patients, encounter chronologies, and outreach station coordinates filtered strictly by the requesting doctor ID.

---

## 5. Database Design and Schema

```sql
-- Clinician accounts
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Patient records (shared across visiting network)
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    health_id VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    age INTEGER,
    gender VARCHAR(20),
    phone VARCHAR(30),
    corridor VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual patient consultations
CREATE TABLE visits (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    visit_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    location VARCHAR(500),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    doctor_name VARCHAR(255),
    notes TEXT,
    medicines TEXT,
    reactions TEXT,
    follow_up TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Outreach field stations ledger
CREATE TABLE field_visits (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
    doctor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    visit_id INTEGER REFERENCES visits(id) ON DELETE SET NULL,
    location VARCHAR(500) NOT NULL,
    location_name VARCHAR(500),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    visit_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    visited_at TIMESTAMP,
    notes TEXT,
    doctor_name VARCHAR(255),
    patients_seen INTEGER DEFAULT 1,
    new_patients INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stored AI continuity analyses
CREATE TABLE ai_analyses (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    summary TEXT,
    past_treatments TEXT,
    medicines TEXT,
    reactions TEXT,
    missed_followups TEXT,
    trends TEXT,
    missing_information TEXT,
    contradictions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. API Specification

All protected endpoints require an `Authorization: Bearer <token>` header.

### Authentication
- `POST /api/auth/login`: Authenticate clinician and receive JWT token.
- `POST /api/auth/register`: Register new clinician profile.
- `GET /api/auth/me`: Validate current session token.
- `GET /api/profile`: Retrieve clinician profile details.

### Patient Directory
- `GET /api/patients`: Search or list recent patients across the network.
- `POST /api/patients`: Register a new patient and generate Health ID.
- `GET /api/patients/{health_id}`: Fetch complete history, encounters, and stored analyses.
- `PUT /api/patients/{health_id}`: Update demographic or contact details.

### Clinical Visits
- `GET /api/visits`: Retrieve visits for an active patient or clinician.
- `POST /api/patients/{health_id}/visits`: Append an encounter to a patient's timeline and record outpost coordinates.
- `GET /api/patients/{health_id}/visits`: Chronological encounter list for a specific patient.

### Field Stations and Cartography
- `GET /api/field-visits`: Return consolidated field stations for the authenticated clinician.
- `POST /api/field-visits`: Direct station logging endpoint.
- `GET /api/config/maps`: Retrieve browser-restricted Google Maps API key from backend environment.

### Intelligence and Optical Recognition
- `POST /api/patients/{health_id}/analyze`: Execute on-demand continuity analysis via Gemini.
- `POST /api/ocr`: Submit image to TrOCR ONNX pipeline for text extraction and field parsing.

### Dossier Archive
- `GET /api/archive`: JSON export of authenticated clinician's records.
- `GET /api/archive/pdf`: Formatted printable PDF dossier generated via ReportLab.

---

## 7. Local Development Setup

### 7.1 Prerequisites
- Python 3.10 or higher
- PostgreSQL 14 or higher running locally
- Git

### 7.2 Clone and Setup Environment
```bash
git clone <repository_url>
cd Arog

# Create and activate Python virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 7.3 Database Initialization
Ensure PostgreSQL is active and create the database:
```sql
CREATE DATABASE "AROG";
```

### 7.4 Configure Environment Variables
Create a `.env` file in the `backend/` directory:
```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/AROG
SECRET_KEY=your_secure_random_jwt_secret_key_minimum_32_characters
GEMINI_API_KEY=your_google_ai_studio_gemini_api_key
GOOGLE_MAPS_API_KEY=your_google_maps_javascript_api_key
```

### 7.5 Run the Development Server
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Access the application at `http://127.0.0.1:8000/`.

---

## 8. Production Deployment Guide

### 8.1 Deploying on Render (Unified Deployment)
The repository includes a `render.yaml` blueprint that deploys the application and database together.

1. Push your repository to GitHub.
2. Sign in to Render (https://render.com).
3. Click **New +** and select **Blueprint**.
4. Connect your GitHub repository.
5. Render detects `render.yaml` and provisions:
   - `arog-db`: Managed PostgreSQL database.
   - `arog-app`: Unified Web Service running FastAPI and static frontend.
6. Under Environment Variables in the Render dashboard, provide:
   - `GEMINI_API_KEY`
   - `GOOGLE_MAPS_API_KEY`
7. Click **Apply**. Render assigns an HTTPS domain with automated SSL certificates, enabling device camera and GPS capabilities immediately.

### 8.2 Deploying with Docker Compose
A standalone production container stack can be launched via Docker Compose:

```bash
docker-compose up -d --build
```

Ensure environment secrets are defined in your host environment or `.env` file prior to execution.

---

## 9. Verification and Testing

The repository contains an end-to-end automated verification suite covering all authorization checks, doctor isolation boundaries, GPS station consolidation, PDF generation, and OCR execution:

```bash
cd backend
python test_e2e_all_requirements.py
python test_merge_same_location.py
```

### Key Verification Cases Covered
- `TEST 1`: Unauthenticated API access verification (enforces HTTP 401 across all protected routes).
- `TEST 2`: Multi-clinician credential authentication.
- `TEST 3`: Doctor A vs. Doctor B field visit data isolation.
- `TEST 4`: Automatic station logging and same-location encounter consolidation.
- `TEST 5`: Clinician-scoped PDF archive generation.
- `TEST 6`: Secure Maps configuration delivery.
- `TEST 7`: Gemini continuity analysis adherence to non-diagnostic constraints.
- `TEST 8`: Non-destructive TrOCR document parsing.

---

## 10. Security and Data Governance

- **Credential Isolation:** API keys, database credentials, and JWT signing keys are stored exclusively in backend environment variables and are excluded from Git via `.gitignore`.
- **Browser-Restricted Map Delivery:** The Maps JavaScript API key is served via an authenticated endpoint (`/api/config/maps`) and restricted to trusted deployment origins.
- **Client Identity Scoping:** Doctor identifiers are extracted directly from verified JWT claims on the server. The backend rejects client-supplied doctor identities in favor of the authenticated session identity.
- **Privacy Standard:** Physical document scans processed through TrOCR run entirely within local process memory and are not stored in unencrypted third-party caches.
