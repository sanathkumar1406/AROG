-- =====================================================================
-- AROG: AI-Powered Continuity of Care Platform
-- PostgreSQL Database Initialization & Migration Script
-- =====================================================================
-- To connect and execute in PostgreSQL CLI:
--   psql -U postgres -h localhost -p 5432 -d postgres
--   CREATE DATABASE "AROG";
--   \c "AROG"
--   \i database_setup.sql
-- =====================================================================

-- 1. Create Tables

-- Table: users (Healthcare Providers / Traveling Doctors)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- Table: patients (Universal Digital Health Identity)
CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    health_id VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    age INTEGER CHECK (age >= 0 AND age <= 150),
    gender VARCHAR(20),
    phone VARCHAR(30),
    corridor VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_patients_health_id ON patients (health_id);
CREATE INDEX IF NOT EXISTS ix_patients_name ON patients (name);

-- Table: visits (Continuous Multi-Clinician Visit Narrative)
CREATE TABLE IF NOT EXISTS visits (
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
CREATE INDEX IF NOT EXISTS ix_visits_patient_id ON visits (patient_id);
CREATE INDEX IF NOT EXISTS ix_visits_doctor_id ON visits (doctor_id);
CREATE INDEX IF NOT EXISTS ix_visits_visit_date ON visits (visit_date);

-- Table: ai_analyses (Clinical Summaries & Contradiction Detection)
CREATE TABLE IF NOT EXISTS ai_analyses (
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
CREATE INDEX IF NOT EXISTS ix_ai_analyses_patient_id ON ai_analyses (patient_id);

-- Table: field_visits (Geographic & Outreach Care Stations)
CREATE TABLE IF NOT EXISTS field_visits (
    id SERIAL PRIMARY KEY,
    location VARCHAR(500) NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    visit_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    doctor_name VARCHAR(255),
    patients_seen INTEGER DEFAULT 0,
    new_patients INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_field_visits_visit_date ON field_visits (visit_date);

-- =====================================================================
-- 2. Seed Initial Demonstration Data
-- =====================================================================

-- Default Doctor User (Password: "DoctorPass123!")
-- bcrypt hash for "DoctorPass123!"
INSERT INTO users (name, email, hashed_password)
VALUES (
    'Dr. Julian M. Aris, MD',
    'doctor@arog.health',
    '$2b$12$K1d0wz04eTjQh1O8X5Gkbe921e1h2u/4K.aZ.2ZpQxI8H7K3.gNyy'
) ON CONFLICT (email) DO NOTHING;

-- Seed Patients
INSERT INTO patients (health_id, name, age, gender, phone, corridor)
VALUES 
('AROG-HC2048', 'Ravi Kumar', 52, 'Male', '+91 98765 43210', 'Southern Transit Route (Circuit #4)'),
('AROG-HC1937', 'Lakshmi Devi', 46, 'Female', '+91 98765 43211', 'Western Ghats Agricultural Belt'),
('AROG-HC2291', 'Anand Verma', 38, 'Male', '+91 98765 43212', 'Northern Valley Corridor')
ON CONFLICT (health_id) DO NOTHING;

-- Seed Visits for Ravi Kumar (health_id = 'AROG-HC2048')
DO $$
DECLARE
    ravi_id INTEGER;
BEGIN
    SELECT id INTO ravi_id FROM patients WHERE health_id = 'AROG-HC2048' LIMIT 1;

    IF ravi_id IS NOT NULL THEN
        -- Visit 1: Initial baseline
        INSERT INTO visits (patient_id, visit_date, location, doctor_name, notes, medicines, reactions, follow_up)
        VALUES (
            ravi_id,
            '2026-01-12 10:30:00',
            'Primary Health Centre (Central Valley)',
            'Dr. Eric Chen',
            'Initial consultation and baseline cardiovascular screening. Established patient digital health identity. Documented onset of Stage 1 hypertension (BP 142/90 mmHg). Patient advised low sodium diet.',
            'Amlodipine 5mg OD (morning)',
            'No known drug allergies reported.',
            'Return in 6 weeks for BP check.'
        );

        -- Visit 2: Mobile Outpost (Conflict introduces Sulfa allergy & dosage reduction)
        INSERT INTO visits (patient_id, visit_date, location, doctor_name, notes, medicines, reactions, follow_up)
        VALUES (
            ravi_id,
            '2026-03-04 14:15:00',
            'Rural Health Camp (Mobile Unit #4)',
            'Dr. Sunita Rao, MBBS',
            'BP 138/88 mmHg. Patient presented with profound muscle fatigue during seasonal agricultural harvest. Amlodipine stopped without tapering. Mild erythematous rash observed on lower extremities after taking Hydrochlorothiazide.',
            'Ramipril 2.5mg OD',
            'Sulfa allergy flagged: cutaneous rash from thiazide diuretic.',
            'Hydration protocol during summer harvest. Follow up in 3 months.'
        );

        -- Visit 3: Recent Outpost Visit (Dosage increased, headache noted)
        INSERT INTO visits (patient_id, visit_date, location, doctor_name, notes, medicines, reactions, follow_up)
        VALUES (
            ravi_id,
            '2026-08-18 11:00:00',
            'Community Health Centre (South Outpost)',
            'Dr. Julian M. Aris, MD',
            'Blood Pressure recorded at 148/92 mmHg. Patient reported recurring late afternoon headaches. Titrated Ramipril to 5mg daily. Ordered follow-up metabolic panel to verify kidney function before dosage adjustment.',
            'Ramipril 5mg OD (morning)',
            'Sulfa allergy documented.',
            'Serum electrolytes and creatinine needed in 45 days.'
        );

        -- Initial AI Analysis for Ravi Kumar
        INSERT INTO ai_analyses (
            patient_id, summary, past_treatments, medicines, reactions,
            missed_followups, trends, missing_information, contradictions
        ) VALUES (
            ravi_id,
            '52-year-old male with persistent hypertension recorded across 3 distinct outreach facilities. Originally started on Amlodipine 5mg by Dr. Chen, later transitioned to Ramipril 2.5mg by Dr. Rao following muscle fatigue, and titrated to Ramipril 5mg by Dr. Aris due to elevated BP (148/92 mmHg).',
            '["Cardiovascular screening (Jan 2026)", "Antihypertensive therapy titration", "Hydration management during agricultural work"]',
            '["Ramipril 5mg once daily", "Amlodipine 5mg (discontinued)"]',
            '["Sulfa allergy: cutaneous erythematous rash reported with thiazide diuretic in Mar 2026"]',
            '["Serum creatinine lab check requested 45 days ago is overdue"]',
            '["BP fluctuation across visits: 142/90 -> 138/88 -> 148/92 mmHg", "Afternoon headaches correlating with peak BP"]',
            '["Amlodipine was stopped at Rural Health Camp, but specific reason for cessation was not documented in clinical notes. Please verify.", "Serum electrolytes lab panel pending before next ACE inhibitor titration. Please verify."]',
            '["Visit 1 (12 Jan 2026) records: No known drug allergies, whereas Visit 2 (04 Mar 2026) documents Sulfa allergy reaction. Please verify with patient."]'
        );
    END IF;
END $$;

-- Seed Field Visits
INSERT INTO field_visits (location, latitude, longitude, visit_date, notes, doctor_name, patients_seen, new_patients)
VALUES
('Khammam District Outpost', 17.2473, 80.1514, '2026-08-08 09:00:00', 'Mobile unit operational at rural community hall. High attendance for hypertension screening.', 'Dr. Julian M. Aris, MD', 14, 3),
('Karimnagar Health Station', 18.4386, 79.1288, '2026-08-12 08:30:00', 'Focus on agricultural worker health checkups and chronic disease ledger renewals.', 'Dr. Julian M. Aris, MD', 17, 2),
('Ananthagiri Ridges Outreach', 17.3110, 77.8680, '2026-08-15 10:00:00', 'Traversed mountain pass circuit. Screened elderly villagers and issued portable Health IDs.', 'Dr. Julian M. Aris, MD', 18, 0),
('Nalgonda ZP Primary Health Post', 17.0575, 79.2684, '2026-08-18 08:00:00', 'Reconciled 2 dual-antihypertensive dosage overlaps across visiting clinic networks before departure.', 'Dr. Julian M. Aris, MD', 24, 6);
