import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Login Doctor A
login_data = json.dumps({'email': 'doctor@arog.health', 'password': 'DoctorPass123!'}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/api/auth/login', data=login_data, headers={'Content-Type': 'application/json'})
token = json.loads(urllib.request.urlopen(req).read().decode())['access_token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# 1. Add visit 1 at 'Khammam Urban Station'
v1_data = json.dumps({
    'location': 'Khammam Urban Station',
    'latitude': 17.2475,
    'longitude': 80.1520,
    'notes': 'Encounter 1: Routine checkup',
    'medicines': 'Paracetamol 500mg',
    'reactions': 'None'
}).encode()
req_v1 = urllib.request.Request('http://127.0.0.1:8000/api/patients/AROG-HC2048/visits', data=v1_data, headers=headers)
res1 = json.loads(urllib.request.urlopen(req_v1).read().decode())
print(f"Visit 1 created: ID={res1['id']}, Location={res1['location']}")

# 2. Add visit 2 at 'Khammam Urban Station' on the SAME day for another patient (AROG-HC1937)
v2_data = json.dumps({
    'location': 'Khammam Urban Station',
    'latitude': 17.2475,
    'longitude': 80.1520,
    'notes': 'Encounter 2: Followup titration',
    'medicines': 'Amlodipine 5mg',
    'reactions': 'None'
}).encode()
req_v2 = urllib.request.Request('http://127.0.0.1:8000/api/patients/AROG-HC1937/visits', data=v2_data, headers=headers)
res2 = json.loads(urllib.request.urlopen(req_v2).read().decode())
print(f"Visit 2 created: ID={res2['id']}, Location={res2['location']}")

# 3. Fetch Field Visits and verify Khammam Urban Station is merged into ONE station
req_fv = urllib.request.Request('http://127.0.0.1:8000/api/field-visits', headers=headers)
fvs = json.loads(urllib.request.urlopen(req_fv).read().decode())

khammam_stations = [v for v in fvs if v['location_name'] == 'Khammam Urban Station']
print(f"Total 'Khammam Urban Station' records returned in field visits: {len(khammam_stations)}")
for s in khammam_stations:
    print(f"  Station: {s['location_name']}")
    print(f"  Patients treated: {s['patients_treated']}")
    print(f"  Patient count: {s['patient_count']}")
    print(f"  Visits count: {s['visits_count']}")

assert len(khammam_stations) == 1, f"Expected exactly 1 merged station, got {len(khammam_stations)}"
assert khammam_stations[0]['patient_count'] >= 2, f"Expected patient_count >= 2, got {khammam_stations[0]['patient_count']}"
assert len(khammam_stations[0]['patients_treated']) >= 2, f"Expected at least 2 patients treated, got {khammam_stations[0]['patients_treated']}"

print("\nSUCCESS: Both encounters at the same location and date merged into 1 station with combined count and patient list!")
