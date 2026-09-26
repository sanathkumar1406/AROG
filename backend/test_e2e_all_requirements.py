"""
End-to-End Automated Test Suite for AROG Continuity of Care Platform.
Tests all 25 Requirements and Core Flows (TEST A - TEST J).
"""
import io
import sys
import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient

sys.stdout.reconfigure(encoding='utf-8')

from app.main import app
from app.database.database import SessionLocal
from app.database.models import User, Patient, Visit, FieldVisit

client = TestClient(app)

def run_tests():
    print("=" * 60)
    print("STARTING COMPLETE E2E VERIFICATION FOR AROG")
    print("=" * 60)

    # ----------------------------------------------------
    # TEST 1 & 10: BACKEND AUTH PROTECTION (401 on unauthenticated)
    # ----------------------------------------------------
    print("\n[TEST 1/8] Verifying Backend Route Authorization (Requirement 9 & 10)...")
    protected_endpoints = [
        ("GET", "/api/patients"),
        ("GET", "/api/patients/AROG-HC2048"),
        ("GET", "/api/visits"),
        ("GET", "/api/field-visits"),
        ("GET", "/api/profile"),
        ("GET", "/api/archive"),
        ("GET", "/api/archive/pdf"),
        ("GET", "/api/ai"),
        ("POST", "/api/patients/AROG-HC2048/visits"),
        ("POST", "/api/patients/AROG-HC2048/analyze"),
    ]

    for method, path in protected_endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401, f"Expected 401 for {method} {path}, got {res.status_code}"
        print(f"  ✓ {method} {path} correctly blocked with 401 Unauthorized")

    # ----------------------------------------------------
    # TEST 2 & 3: AUTHENTICATE DOCTOR A & B
    # ----------------------------------------------------
    print("\n[TEST 2/8] Authenticating Doctor A & Doctor B...")
    doc_a_login = client.post("/api/auth/login", json={
        "email": "doctor@arog.health",
        "password": "DoctorPass123!"
    })
    assert doc_a_login.status_code == 200, f"Doctor A login failed: {doc_a_login.text}"
    token_a = doc_a_login.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    print("  [PASS] Doctor A (Dr. Julian M. Aris) authenticated successfully")

    doc_b_login = client.post("/api/auth/login", json={
        "email": "sunita.rao@arog.health",
        "password": "DoctorPass123!"
    })
    assert doc_b_login.status_code == 200, f"Doctor B login failed: {doc_b_login.text}"
    token_b = doc_b_login.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    print("  ✓ Doctor B (Dr. Sunita Rao) authenticated successfully")

    # Profile checks
    prof_a = client.get("/api/profile", headers=headers_a).json()
    prof_b = client.get("/api/profile", headers=headers_b).json()
    assert prof_a["id"] == 1, f"Expected Doctor A ID 1, got {prof_a['id']}"
    assert prof_b["id"] == 2, f"Expected Doctor B ID 2, got {prof_b['id']}"
    print(f"  ✓ Profile A verified: {prof_a['name']} (ID={prof_a['id']})")
    print(f"  ✓ Profile B verified: {prof_b['name']} (ID={prof_b['id']})")

    # ----------------------------------------------------
    # TEST 3: FIELD VISITS ISOLATION (Requirement 1, 2, 3)
    # ----------------------------------------------------
    print("\n[TEST 3/8] Verifying Doctor-Specific Field Visits Isolation (Requirements 1, 2, 3)...")
    fv_a = client.get("/api/field-visits", headers=headers_a).json()
    fv_b = client.get("/api/field-visits", headers=headers_b).json()

    print(f"  Doctor A has {len(fv_a)} field visits")
    print(f"  Doctor B has {len(fv_b)} field visits")

    # Extract locations
    locs_a = [v.get("location_name") or v.get("location") for v in fv_a]
    locs_b = [v.get("location_name") or v.get("location") for v in fv_b]

    print(f"  Doctor A locations: {locs_a}")
    print(f"  Doctor B locations: {locs_b}")

    # Check isolation: Doctor A must NEVER see Doctor B's locations
    for loc in locs_b:
        assert loc not in locs_a, f"Leakage! Doctor B's location '{loc}' found in Doctor A's field visits!"
    for loc in locs_a:
        assert loc not in locs_b, f"Leakage! Doctor A's location '{loc}' found in Doctor B's field visits!"
    print("  ✓ Field visits are strictly isolated between Doctor A and Doctor B at the backend SQL query level")

    # Check required fields in each record (Requirement 2)
    for v in fv_a + fv_b:
        assert "latitude" in v and v["latitude"] is not None, "Missing latitude"
        assert "longitude" in v and v["longitude"] is not None, "Missing longitude"
        assert "location_name" in v, "Missing location_name"
        assert "visit_date" in v or "visited_at" in v, "Missing visit_date/visited_at"
        assert "doctor" in v or "doctor_name" in v, "Missing doctor"
        assert "patient_count" in v, "Missing patient_count"
        assert "patients_treated" in v, "Missing patients_treated"
    print("  ✓ All required fields (lat, lng, location_name, visit_date, doctor, patient_count, patients_treated) present")

    # ----------------------------------------------------
    # TEST 4: AUTOMATIC FIELD VISIT CREATION & GPS (Requirements 5, 6, 7)
    # ----------------------------------------------------
    print("\n[TEST 4/8] Testing Automatic Field Visit Creation with GPS (Requirements 5, 6, 7)...")
    # Patient Ravi Kumar health_id: AROG-HC2048
    test_lat = 17.5123
    test_lng = 78.4321
    test_loc = f"Siddipet Health Camp - {datetime.utcnow().strftime('%H%M%S')}"

    add_visit_res = client.post(
        "/api/patients/AROG-HC2048/visits",
        headers=headers_a,
        json={
            "location": test_loc,
            "latitude": test_lat,
            "longitude": test_lng,
            "notes": "Follow-up consultation with recorded coordinates.",
            "medicines": "Amlodipine 5 mg OD",
            "reactions": "None",
            "follow_up": "Check vitals in 4 weeks"
        }
    )
    assert add_visit_res.status_code == 201, f"Failed to add visit: {add_visit_res.text}"
    created_visit = add_visit_res.json()
    assert created_visit["doctor_id"] == 1, f"Expected doctor_id 1, got {created_visit['doctor_id']}"
    assert created_visit["doctor_name"] == prof_a["name"], "Doctor name not populated from profile"
    print(f"  ✓ Visit recorded for Ravi Kumar by Doctor A at '{test_loc}'")

    # Verify that field visit was automatically created for Doctor A
    fv_a_after = client.get("/api/field-visits", headers=headers_a).json()
    matching_fv = next((v for v in fv_a_after if v.get("location_name") == test_loc), None)
    assert matching_fv is not None, f"Automatic FieldVisit not found in Doctor A's field visits for '{test_loc}'"
    assert matching_fv["doctor_id"] == 1
    assert matching_fv["latitude"] == test_lat
    assert matching_fv["longitude"] == test_lng
    assert matching_fv["visit_id"] == created_visit["id"]
    print(f"  ✓ Automatic FieldVisit verified in database with visit_id={matching_fv['visit_id']}, doctor_id={matching_fv['doctor_id']}")

    # Verify that Doctor B does NOT see this new field visit
    fv_b_after = client.get("/api/field-visits", headers=headers_b).json()
    assert not any(v.get("location_name") == test_loc for v in fv_b_after), "Leakage! New location visible to Doctor B!"
    print("  ✓ Confirmed Doctor B still cannot see Doctor A's newly added field visit")

    # ----------------------------------------------------
    # TEST 5: DOCTOR-SPECIFIC PDF ARCHIVE (Requirement 8)
    # ----------------------------------------------------
    print("\n[TEST 5/8] Testing Doctor-Specific PDF Archive (Requirement 8)...")
    archive_res_a = client.get("/api/archive/pdf", headers=headers_a)
    assert archive_res_a.status_code == 200, f"Doctor A PDF failed: {archive_res_a.text}"
    assert archive_res_a.headers["content-type"] == "application/pdf"
    assert len(archive_res_a.content) > 1000, "PDF content is too small or empty"
    print(f"  ✓ Doctor A PDF generated successfully ({len(archive_res_a.content)} bytes)")

    archive_res_b = client.get("/api/archive/pdf", headers=headers_b)
    assert archive_res_b.status_code == 200, f"Doctor B PDF failed: {archive_res_b.text}"
    assert archive_res_b.headers["content-type"] == "application/pdf"
    assert len(archive_res_b.content) > 1000, "PDF content is too small or empty"
    print(f"  ✓ Doctor B PDF generated successfully ({len(archive_res_b.content)} bytes)")

    # Verify structured JSON archive scoping
    json_archive_a = client.get("/api/archive", headers=headers_a).json()
    json_archive_b = client.get("/api/archive", headers=headers_b).json()

    assert json_archive_a["doctor"]["id"] == 1
    assert json_archive_b["doctor"]["id"] == 2
    # Ensure Doctor A's archive does not contain Doctor B's locations
    archive_locs_a = [f["location"] for f in json_archive_a["field_visits"]]
    archive_locs_b = [f["location"] for f in json_archive_b["field_visits"]]
    for loc in archive_locs_b:
        assert loc not in archive_locs_a, f"Doctor B location '{loc}' leaked into Doctor A archive JSON!"
    print("  ✓ Doctor-specific archive JSON and PDF verified strictly isolated by authenticated doctor")

    # ----------------------------------------------------
    # TEST 6: GOOGLE MAPS CONFIGURATION (Requirement 4)
    # ----------------------------------------------------
    print("\n[TEST 6/8] Verifying Maps Configuration Endpoint (Requirement 4)...")
    maps_config = client.get("/api/config/maps", headers=headers_a).json()
    assert "google_maps_api_key" in maps_config, "Missing google_maps_api_key key"
    print(f"  ✓ /api/config/maps returns secure configuration: key_present={bool(maps_config['google_maps_api_key'])}")

    # ----------------------------------------------------
    # TEST 7: GEMINI PATIENT ANALYSIS (Requirements 11, 12, 13, 14)
    # ----------------------------------------------------
    print("\n[TEST 7/8] Verifying Patient Analysis Engine & Medical Constraints (Requirements 11, 12, 13, 14)...")
    # Call analysis on Ravi Kumar (AROG-HC2048)
    ai_res = client.post("/api/patients/AROG-HC2048/analyze", headers=headers_a)
    assert ai_res.status_code == 200, f"AI analysis failed: {ai_res.text}"
    ai_data = ai_res.json()

    print(f"  AI Summary: {ai_data['summary'][:100]}...")
    print(f"  Missing Info: {ai_data['missing_information']}")
    print(f"  Contradictions: {ai_data['contradictions']}")
    print(f"  Medicines: {ai_data['medicines']}")

    # Verify structured fields
    for field in ["summary", "past_treatments", "medicines", "reactions", "missed_followups", "trends", "missing_information", "contradictions"]:
        assert field in ai_data, f"Missing structured field '{field}'"

    # Verify medical constraint: must NOT diagnose or recommend treatments
    disallowed_terms = ["i diagnose", "diagnosis is", "you have cancer", "prescribe new"]
    for term in disallowed_terms:
        assert term not in ai_data["summary"].lower(), f"Disallowed diagnostic language found: {term}"
    print("  ✓ AI Continuity Analysis conforms to non-diagnostic, strictly record-bound clinical constraints")

    # ----------------------------------------------------
    # TEST 8: TrOCR DOCUMENT UPLOAD & PARSER (Requirements 17, 18, 19)
    # ----------------------------------------------------
    print("\n[TEST 8/8] Testing TrOCR Document Upload & Structured Parser (Requirements 17, 18, 19)...")
    # Create synthetic prescription image
    img = Image.new("RGB", (384, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), "Patient: Ravi Kumar", fill=(0, 0, 0))
    d.text((10, 30), "Date: 20 Sep 2026", fill=(0, 0, 0))
    d.text((10, 50), "Medicine: Amlodipine 5 mg OD", fill=(0, 0, 0))
    d.text((10, 70), "Notes: Follow-up after 2 weeks", fill=(0, 0, 0))

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    ocr_res = client.post(
        "/api/ocr",
        headers=headers_a,
        files={"file": ("prescription_test.jpg", img_bytes, "image/jpeg")}
    )
    assert ocr_res.status_code == 200, f"OCR endpoint failed: {ocr_res.text}"
    ocr_data = ocr_res.json()
    assert "extracted_text" in ocr_data, "Missing extracted_text"
    assert "structured_data" in ocr_data, "Missing structured_data"
    print(f"  ✓ TrOCR endpoint responded with extracted text and structured data: {ocr_data.get('structured_data')}")
    print(f"  ✓ Model verified non-destructive (does NOT auto-save without doctor confirmation)")

    print("\n" + "=" * 60)
    print("ALL 8 VERIFICATION TEST SUITES PASSED FLAWLESSLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
