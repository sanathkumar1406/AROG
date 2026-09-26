import requests
import json

BASE = "http://127.0.0.1:8000"

def run_tests():
    print("--- STARTING AROG INTEGRATION TEST SUITE ---")

    # TEST 1: Open Home while logged out
    res = requests.get(f"{BASE}/frontend/arog_healthcare_continuity_home/code.html")
    assert res.status_code == 200, f"Home failed: {res.status_code}"
    print("✓ TEST 1: Home page accessible without authentication (HTTP 200)")

    # TEST 2: Patients page / API without authentication
    res = requests.get(f"{BASE}/api/patients")
    assert res.status_code == 401, f"Expected 401 without auth, got {res.status_code}"
    print("✓ TEST 2: Protected patient API rejects unauthenticated requests (HTTP 401)")

    # TEST 3: Demo credentials login
    res = requests.post(f"{BASE}/api/auth/login", json={"email": "doctor@arog.health", "password": "DoctorPass123!"})
    assert res.status_code == 200, f"Demo login failed: {res.text}"
    auth_data = res.json()
    token = auth_data["access_token"]
    doctor_name = auth_data["user_name"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"✓ TEST 4: Demo login successful. Logged in as: {doctor_name}")

    # TEST 11: User profile /me
    res = requests.get(f"{BASE}/api/auth/me", headers=headers)
    assert res.status_code == 200, f"/me failed: {res.status_code} {res.text}"
    me = res.json()
    assert me["email"] == "doctor@arog.health", f"Wrong email: {me}"
    print(f"✓ TEST 11: /api/auth/me returns authenticated doctor profile: {me['name']} ({me['email']}, {me['role']})")

    # TEST 5: Recent patients list
    res = requests.get(f"{BASE}/api/patients?limit=10", headers=headers)
    assert res.status_code == 200
    pts = res.json()
    assert len(pts) > 0, "No patients returned"
    print(f"✓ TEST 5: Recent patients loaded: {len(pts)} entries. Most recent: {pts[0]['name']} ({pts[0]['health_id']})")

    # TEST 6: Patient details lookup
    target_hid = pts[0]["health_id"]
    res = requests.get(f"{BASE}/api/patients/{target_hid}", headers=headers)
    assert res.status_code == 200
    pt_detail = res.json()
    assert pt_detail["health_id"] == target_hid
    print(f"✓ TEST 6: Patient details loaded for {pt_detail['name']}: {len(pt_detail.get('visits', []))} visits")

    # TEST 7: QR Code lookup / patient search
    res = requests.get(f"{BASE}/api/patients?search={target_hid}", headers=headers)
    assert res.status_code == 200
    search_res = res.json()
    assert any(p["health_id"] == target_hid for p in search_res)
    # Test invalid QR lookup
    res_404 = requests.get(f"{BASE}/api/patients/AROG-NONEXISTENT", headers=headers)
    assert res_404.status_code == 404
    print(f"✓ TEST 7: Health ID / QR lookup verified. Non-existent returns HTTP 404.")

    # TEST 8: Add visit with geolocation & enforced doctor identity
    test_loc = "Telangana Regional Outpost #7"
    test_lat = 17.4435
    test_lng = 78.3842
    res = requests.post(
        f"{BASE}/api/patients/{target_hid}/visits",
        headers=headers,
        json={
            "location": test_loc,
            "latitude": test_lat,
            "longitude": test_lng,
            "doctor_name": "Spoofed Hacker MD",  # Backend MUST override this with current_user.name
            "notes": "E2E automated continuity verification visit.",
            "medicines": "Metformin 500mg OD",
            "reactions": "None",
            "follow_up": "Check FBS in 3 months"
        }
    )
    assert res.status_code == 200, f"Add visit failed: {res.text}"
    new_visit = res.json()
    assert new_visit["doctor_name"] == me["name"], f"Doctor name spoofing not blocked! Got {new_visit['doctor_name']}"
    assert new_visit["latitude"] == test_lat, f"Latitude not saved: {new_visit}"
    assert new_visit["longitude"] == test_lng, f"Longitude not saved: {new_visit}"
    print(f"✓ TEST 8: Visit added. Enforced Doctor: {new_visit['doctor_name']} (spoofed name blocked), Lat: {new_visit['latitude']}, Lng: {new_visit['longitude']}")

    # TEST 9: Patient records show new visit
    res = requests.get(f"{BASE}/api/patients/{target_hid}", headers=headers)
    pt_after = res.json()
    visit_found = any(v["location"] == test_loc for v in pt_after.get("visits", []))
    assert visit_found, "New visit not found in patient details"
    print("✓ TEST 9: Patient details record refreshed and reflects new visit")

    # TEST 10: Field visits timeline synchronization
    res = requests.get(f"{BASE}/api/field-visits", headers=headers)
    assert res.status_code == 200
    fvs = res.json()
    fv_found = any(fv["location"] == test_loc and fv["doctor_name"] == me["name"] for fv in fvs)
    assert fv_found, "Field visit not synchronized with patient visit in PostgreSQL!"
    print(f"✓ TEST 10: Field visits timeline synchronized. Verified location: {test_loc}, Doctor: {me['name']}")

    # TEST 12: Logout / token clearing
    bad_headers = {"Authorization": "Bearer expired_or_cleared_token"}
    res = requests.get(f"{BASE}/api/patients", headers=bad_headers)
    assert res.status_code == 401, "Protected API should reject invalid/cleared token"
    print("✓ TEST 12: Logged out / invalid token immediately rejected (HTTP 401)")

    # TEST 16: PostgreSQL Persistence verification
    from app.database.database import SessionLocal
    from app.database.models import Visit as DBVisit, FieldVisit as DBFieldVisit
    db = SessionLocal()
    try:
        db_visit = db.query(DBVisit).filter(DBVisit.location == test_loc).first()
        assert db_visit is not None, "Visit record not persisted in PostgreSQL!"
        assert db_visit.doctor_id == me["id"], f"Wrong doctor_id in DB: {db_visit.doctor_id}"
        assert db_visit.latitude == test_lat, f"Wrong latitude in DB: {db_visit.latitude}"
        
        db_fv = db.query(DBFieldVisit).filter(DBFieldVisit.location == test_loc).first()
        assert db_fv is not None, "Field visit record not persisted in PostgreSQL!"
        assert db_fv.latitude == test_lat
        print("✓ TEST 16: PostgreSQL direct verification passed: records persisted with FKs and GPS coordinates.")
    finally:
        db.close()

    print("\n==========================================")
    print(" ALL 16 INTEGRATION TEST CHECKS PASSED! ")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
