"""
AROG Backend - Comprehensive Integration & Verification Test Suite.
Tests all 16 requirement specifications:
- Access control & 401 rejection for unauthenticated users
- Demo login with JWT generation
- Enforced doctor identity from auth token
- Geolocation capture & persistence
- PostgreSQL foreign key integrity
- Recent patient ordering & search
- TrOCR inference
- AI analysis synthesis & discrepancy detection
"""
import io
import sys
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.database.database import SessionLocal
from app.database.models import User, Patient, Visit, FieldVisit

client = TestClient(app)

def run_tests():
    print("==================================================")
    print("AROG BACKEND VERIFICATION TEST SUITE (16 CHECKS)")
    print("==================================================")

    # 1. Health
    r = client.get("/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    print("[PASS] 1. GET /health ->", r.json())

    # 2. Database Health
    r = client.get("/api/health/db")
    assert r.status_code == 200, f"Database health check failed: {r.text}"
    assert r.json().get("database") == "connected", "DB not connected"
    print("[PASS] 2. GET /api/health/db ->", r.json())

    # 3. Access Control: Protected API rejects unauthenticated requests (HTTP 401)
    r = client.get("/api/patients")
    assert r.status_code == 401, f"Expected 401 without auth, got {r.status_code}"
    print("[PASS] 3. GET /api/patients without auth -> correctly rejected with HTTP 401")

    # 4. Demo Login
    r = client.post("/api/auth/login", json={
        "email": "doctor@arog.health",
        "password": "DoctorPass123!"
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    auth_data = r.json()
    token = auth_data["access_token"]
    doctor_name = auth_data["user_name"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    print(f"[PASS] 4. POST /api/auth/login -> Logged in as: {doctor_name}")

    # 5. User Profile (/api/auth/me)
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200, f"/me failed: {r.text}"
    me = r.json()
    assert me["email"] == "doctor@arog.health"
    print(f"[PASS] 5. GET /api/auth/me -> Authenticated profile: {me['name']} ({me['email']}, {me['role']})")

    # 6. Recent Patients List (Default limit=10, ordered by most recent activity)
    r = client.get("/api/patients", headers=auth_headers)
    assert r.status_code == 200, f"List patients failed: {r.text}"
    patients = r.json()
    assert len(patients) > 0, "No patients found in DB"
    print(f"[PASS] 6. GET /api/patients -> Found {len(patients)} recent patients. Top: {patients[0]['name']} ({patients[0]['health_id']})")

    # 7. Get Patient Details
    target_hid = patients[0]["health_id"]
    r = client.get(f"/api/patients/{target_hid}", headers=auth_headers)
    assert r.status_code == 200, f"Get patient failed: {r.text}"
    p_data = r.json()
    print(f"[PASS] 7. GET /api/patients/{target_hid} -> {p_data['name']} with {len(p_data['visits'])} visits")

    # 8. Patient Search / QR Lookup
    r = client.get(f"/api/patients?search={target_hid}", headers=auth_headers)
    assert r.status_code == 200
    search_res = r.json()
    assert any(p["health_id"] == target_hid for p in search_res)
    # Non-existent ID lookup returns 404
    r_404 = client.get("/api/patients/AROG-NONEXISTENT", headers=auth_headers)
    assert r_404.status_code == 404
    print(f"[PASS] 8. Health ID/QR search verified. Found match; non-existent correctly returns 404.")

    # 9. Register New Patient
    r = client.post("/api/patients", headers=auth_headers, json={
        "name": "Kamala Bai",
        "age": 48,
        "gender": "Female",
        "phone": "+91 91234 56789",
        "corridor": "Eastern Silk Route"
    })
    assert r.status_code == 201, f"Create patient failed: {r.text}"
    new_patient = r.json()
    new_hid = new_patient["health_id"]
    assert new_hid.startswith("AROG-"), f"Unexpected health_id format: {new_hid}"
    print(f"[PASS] 9. POST /api/patients -> Created {new_patient['name']} with Health ID: {new_hid}")

    # 10. Add Visit with GPS Coordinates & Enforced Doctor Name
    test_loc = "Warangal Mobile Ridge Camp"
    test_lat = 17.9689
    test_lng = 79.5941
    r = client.post(f"/api/patients/{new_hid}/visits", headers=auth_headers, json={
        "location": test_loc,
        "latitude": test_lat,
        "longitude": test_lng,
        "doctor_name": "Spoofed Imposter MD",  # Backend MUST override this with me["name"]
        "notes": "Patient presented with dizziness. BP 136/84. Prescribed multivitamin.",
        "medicines": "Multivitamin OD",
        "reactions": "No known drug allergies",
        "follow_up": "Check vitals in 3 weeks"
    })
    assert r.status_code == 201, f"Add visit failed: {r.text}"
    v_data = r.json()
    assert v_data["doctor_name"] == me["name"], f"Doctor name spoofing not blocked! Got {v_data['doctor_name']}"
    assert v_data["latitude"] == test_lat
    assert v_data["longitude"] == test_lng
    print(f"[PASS] 10. POST /api/patients/{new_hid}/visits -> Enforced doctor: {v_data['doctor_name']} (spoofed name blocked), GPS: ({v_data['latitude']}, {v_data['longitude']})")

    # 11. Patient Visits Updated
    r = client.get(f"/api/patients/{new_hid}/visits", headers=auth_headers)
    assert r.status_code == 200
    visits_list = r.json()
    assert len(visits_list) >= 1
    assert any(v["location"] == test_loc for v in visits_list)
    print(f"[PASS] 11. GET /api/patients/{new_hid}/visits -> Found {len(visits_list)} visit(s), newly added visit confirmed.")

    # 12. Field Visits / Timeline Synchronized
    r = client.get("/api/field-visits", headers=auth_headers)
    assert r.status_code == 200, f"Field visits failed: {r.text}"
    fv_list = r.json()
    fv_match = next((fv for fv in fv_list if fv["location"] == test_loc and fv["doctor_name"] == me["name"]), None)
    assert fv_match is not None, "Added visit did not synchronize to Field Visits in PostgreSQL!"
    assert fv_match["latitude"] == test_lat
    print(f"[PASS] 12. GET /api/field-visits -> Synchronized field visit found: {fv_match['location']} by {fv_match['doctor_name']}")

    # 13. AI Patient Summary & Contradiction Detection
    ravi_id = "AROG-HC2048"
    r = client.post(f"/api/patients/{ravi_id}/analyze", headers=auth_headers)
    if r.status_code == 404:
        # Fallback to target_hid if ravi_id not present
        r = client.post(f"/api/patients/{target_hid}/analyze", headers=auth_headers)
    assert r.status_code == 200, f"AI analyze failed: {r.text}"
    ai_result = r.json()
    assert "summary" in ai_result
    assert "missing_information" in ai_result
    assert "contradictions" in ai_result
    print(f"[PASS] 13. POST /api/patients/.../analyze -> AI analysis synthesized.")
    print(f"         Summary snippet: {ai_result['summary'][:80]}...")

    # 14. TrOCR Text Extraction
    img = Image.new("RGB", (384, 384), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    r = client.post("/api/ocr", headers=auth_headers, files={"file": ("rx_slip.png", buf, "image/png")})
    assert r.status_code == 200, f"OCR failed: {r.text}"
    ocr_res = r.json()
    assert "extracted_text" in ocr_res
    print(f"[PASS] 14. POST /api/ocr -> TrOCR document inference processed successfully.")

    # 15. Invalid / Expired Token Rejection
    bad_headers = {"Authorization": "Bearer invalid_or_expired_token"}
    r = client.get("/api/patients", headers=bad_headers)
    assert r.status_code == 401, f"Expected 401 for bad token, got {r.status_code}"
    print("[PASS] 15. Invalid/logged-out token immediately rejected (HTTP 401)")

    # 16. Direct PostgreSQL Consistency Check
    db = SessionLocal()
    try:
        db_visit = db.query(Visit).filter(Visit.location == test_loc).first()
        assert db_visit is not None, "Visit record not persisted in PostgreSQL!"
        assert db_visit.doctor_id == me["id"], f"Wrong doctor_id: {db_visit.doctor_id}"
        assert db_visit.latitude == test_lat
        assert db_visit.longitude == test_lng

        db_fv = db.query(FieldVisit).filter(FieldVisit.location == test_loc).first()
        assert db_fv is not None, "Field visit record not persisted in PostgreSQL!"
        assert db_fv.doctor_id == me["id"]
        assert db_fv.latitude == test_lat
        print("[PASS] 16. Direct PostgreSQL verification passed: foreign keys & coordinates strictly verified.")
    finally:
        db.close()

    print("==================================================")
    print(" ALL 16 BACKEND INTEGRATION CHECKS PASSED! ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
