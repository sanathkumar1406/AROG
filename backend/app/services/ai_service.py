"""
AROG AI Service - Patient summary, missing info, and contradiction detection.
Uses Google Gemini API with built-in clinical continuity analysis fallback.
Never diagnoses. Doctor always decides.
"""
import os
import re
import json
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SYSTEM_PROMPT = """You are a clinical continuity records assistant for AROG, a Continuity of Care platform used by travelling doctors.

CRITICAL MEDICAL & CONTINUITY CONSTRAINTS (STRICTLY ENFORCED):
- You MUST NOT diagnose any condition or disease.
- You MUST NOT prescribe or recommend any treatment, dosage, or medication.
- You MUST NOT invent, guess, hallucinate, or extrapolate reasons or dosages.
- When displaying medication information, only include information explicitly recorded in the patient's records.
- If a dosage is missing in the records, state: "Dosage not recorded." Do NOT guess dosage.
- If a medicine was stopped/discontinued and no reason is documented in the records, state: "Reason for stopping not recorded." (or "Reason not documented."). Do NOT fabricate an explanation.
- Clearly note whether/when a medicine was stopped and what was used most recently.
- Clearly identify contradictions between encounters (e.g. allergy conflict across visits, dosage conflict) for physician verification. Never decide which is correct.
- Highlight missing information (e.g. lab results pending, reason for stopping medicine not recorded).
- The doctor makes ALL medical decisions.

Your role is strictly to:
1. Summarize the patient's visit history clearly and chronologically across different travelling clinics and outposts.
2. List past treatments and medicines used (with what was used most recently, whether/when stopped, and noting "Dosage not recorded" if dosage is absent).
3. List reported reactions/allergies from records.
4. Identify missed follow-ups (follow-ups mentioned but overdue or unresolved).
5. Identify trends (e.g., escalating BP readings across visits).
6. Detect MISSING information (e.g., "Medicine X was stopped on [Date], but reason for stopping not recorded. Please verify with patient.").
7. Detect CONTRADICTIONS (e.g., "Penicillin allergy is not recorded in the earlier visit on [Date], but is mentioned in a later visit on [Date]. Please verify the correct allergy history.").

Return your response as valid JSON with this exact structure:
{
  "summary": "A concise chronological clinical summary of the patient's journey across visiting posts",
  "past_treatments": ["treatment 1", "treatment 2"],
  "medicines": ["medicine 1 (status: active/stopped, dosage: recorded dosage or 'Dosage not recorded')", "medicine 2 ..."],
  "reactions": ["reaction 1", "reaction 2"],
  "missed_followups": ["description of missed followup 1"],
  "trends": ["trend observation 1"],
  "missing_information": ["missing item 1 (e.g. 'Reason for stopping [Med] not recorded. Please verify.')"],
  "contradictions": ["contradiction description 1 (e.g. 'Allergy conflict: ... Please verify with patient.')"]
}

If a category has no items, return an empty array for that field.
Return ONLY the JSON object, no markdown code block backticks, no text outside the JSON.
"""



def build_patient_context(patient_name: str, health_id: str, visits: list) -> str:
    """Build a text context from patient visits for the AI prompt."""
    lines = [
        f"Patient: {patient_name}",
        f"Health ID: {health_id}",
        f"Total Visits: {len(visits)}",
        "",
        "=== VISIT RECORDS (Chronological) ===",
    ]

    for i, visit in enumerate(visits, 1):
        v_date = visit.visit_date.strftime("%d %b %Y") if hasattr(visit.visit_date, "strftime") else str(visit.visit_date)
        lines.append(f"\n--- Visit {i} ---")
        lines.append(f"Date: {v_date}")
        lines.append(f"Location: {visit.location or 'Not recorded'}")
        lines.append(f"Doctor: {visit.doctor_name or 'Not recorded'}")
        lines.append(f"Notes: {visit.notes or 'None'}")
        lines.append(f"Medicines: {visit.medicines or 'None recorded'}")
        lines.append(f"Reactions: {visit.reactions or 'None recorded'}")
        lines.append(f"Follow-up: {visit.follow_up or 'None specified'}")

    return "\n".join(lines)


def _clinical_rules_analyzer(patient_name: str, health_id: str, visits: list) -> dict:
    """
    Intelligent Clinical Continuity Rule Engine.
    Operates when LLM API is unavailable, rate-limited, or unconfigured.
    Never diagnoses. Synthesizes records, extracts trends, detects missing info and contradictions.
    """
    if not visits:
        return {
            "summary": f"No clinical visit records found for patient {patient_name} ({health_id}).",
            "past_treatments": [],
            "medicines": [],
            "reactions": [],
            "missed_followups": [],
            "trends": [],
            "missing_information": ["No prior visits documented in continuous ledger."],
            "contradictions": [],
        }

    past_treatments = []
    medicines = []
    reactions = []
    missed_followups = []
    trends = []
    missing_info = []
    contradictions = []

    bp_readings = []
    locations = set()
    doctors = set()
    all_allergies_text = []

    # Sort visits chronologically
    sorted_visits = sorted(visits, key=lambda v: str(v.visit_date))

    # Track medication timeline
    med_occurrences = {}

    for idx, v in enumerate(sorted_visits, 1):
        v_date = v.visit_date.strftime("%d %b %Y") if hasattr(v.visit_date, "strftime") else str(v.visit_date)[:10]
        loc = v.location or "Field Outpost"
        doc = v.doctor_name or "Attending Physician"
        locations.add(loc)
        doctors.add(doc)

        # Extract BP
        if v.notes:
            bp_match = re.search(r'\b(BP|Blood Pressure)[:\s]*([0-9]{2,3}/[0-9]{2,3})\b', v.notes, re.IGNORECASE)
            if bp_match:
                bp_readings.append(f"{bp_match.group(2)} mmHg ({v_date} at {loc})")

        # Medicines
        if v.medicines and v.medicines.strip() and v.medicines.lower() != "none":
            for m in re.split(r'[,;\n]+', v.medicines):
                m_clean = m.strip()
                if m_clean and m_clean not in medicines:
                    medicines.append(m_clean)
                    med_occurrences[m_clean] = idx

        # Reactions / Allergies
        if v.reactions and v.reactions.strip() and v.reactions.lower() != "none":
            all_allergies_text.append((v_date, doc, v.reactions.strip()))
            if v.reactions.strip() not in reactions:
                reactions.append(v.reactions.strip())

        # Notes as past treatments
        if v.notes and len(v.notes) > 10:
            past_treatments.append(f"{v_date} ({loc}): {v.notes[:120]}...")

        # Follow up
        if v.follow_up and v.follow_up.strip() and v.follow_up.lower() != "none":
            # If this is not the most recent visit, check if follow up was addressed
            if idx < len(sorted_visits):
                missed_followups.append(f"Follow-up scheduled on {v_date} ('{v.follow_up}') requires reconciliation with subsequent encounters.")
            else:
                missed_followups.append(f"Upcoming follow-up pending: {v.follow_up} (noted by {doc})")

    # Detect Missing Information
    # 1. Stopped medicines without documented reason
    for idx, v in enumerate(sorted_visits):
        if v.notes:
            stopped_match = re.search(r'([A-Za-z0-9]+)\s+(stopped|discontinued|ceased|held)', v.notes, re.IGNORECASE)
            if stopped_match:
                med_name = stopped_match.group(1)
                missing_info.append(f"{med_name} was marked stopped/discontinued, but reason for stopping not recorded. Please verify with patient.")

    # 2. Lab tests or screenings pending without recorded results
    for v in sorted_visits:
        if v.notes:
            test_match = re.search(r'(creatinine|electrolytes|panel|ecg|x-ray|blood test|urine|hba1c)\s+(pending|ordered|needed|due)', v.notes, re.IGNORECASE)
            if test_match:
                missing_info.append(f"{test_match.group(1).title()} was ordered or flagged as pending, but test results are not documented in the record. Please verify.")

    # Detect Contradictions
    # 1. Allergy conflicts across visits
    has_no_allergy = False
    has_specific_allergy = False
    no_allergy_detail = ""
    specific_allergy_detail = ""

    for v_date, doc, text in all_allergies_text:
        low = text.lower()
        if "no known" in low or "nil" in low or "none" in low:
            has_no_allergy = True
            no_allergy_detail = f"Record on {v_date} ({doc}) indicates: '{text}'"
        elif "allergy" in low or "rash" in low or "reaction" in low or "sensitive" in low:
            has_specific_allergy = True
            specific_allergy_detail = f"Record on {v_date} ({doc}) documents: '{text}'"

    if has_no_allergy and has_specific_allergy:
        contradictions.append(f"Allergy conflict detected: {no_allergy_detail}, while {specific_allergy_detail}. Please verify with patient before prescribing.")

    # Trends
    if len(bp_readings) >= 2:
        trends.append(f"Blood pressure progression across visits: {' -> '.join(bp_readings)}")
    elif bp_readings:
        trends.append(f"Documented BP: {bp_readings[0]}")

    if len(locations) > 1:
        trends.append(f"Continuity transit across {len(locations)} outreach posts: {', '.join(locations)}")

    # Summary
    first_date = sorted_visits[0].visit_date.strftime("%d %b %Y") if hasattr(sorted_visits[0].visit_date, "strftime") else str(sorted_visits[0].visit_date)[:10]
    last_date = sorted_visits[-1].visit_date.strftime("%d %b %Y") if hasattr(sorted_visits[-1].visit_date, "strftime") else str(sorted_visits[-1].visit_date)[:10]
    
    summary = (
        f"Continuous medical record for {patient_name} ({health_id}) spanning {len(sorted_visits)} recorded visits "
        f"from {first_date} to {last_date} across {len(locations)} clinical locations ({', '.join(locations)}). "
        f"Recorded care involved {len(doctors)} attending physicians ({', '.join(doctors)}). "
        f"Active pharmacotherapy includes: {', '.join(medicines[:3]) if medicines else 'No active prescriptions documented'}. "
        f"Key continuity focus: {missing_info[0] if missing_info else 'Reconcile clinical notes across visiting posts'}."
    )

    if not missing_info:
        missing_info.append("Verify completeness of recent vital signs and adherence to prescribed regimen.")

    return {
        "summary": summary,
        "past_treatments": past_treatments[:4],
        "medicines": medicines,
        "reactions": reactions,
        "missed_followups": missed_followups,
        "trends": trends,
        "missing_information": missing_info,
        "contradictions": contradictions,
    }


async def analyze_patient(patient_name: str, health_id: str, visits: list) -> dict:
    """
    Analyze patient records using Gemini API with intelligent clinical continuity fallback.
    Returns structured analysis dict.
    The AI NEVER diagnoses. It only summarizes, detects missing info, and flags contradictions.
    """
    if not visits:
        return {
            "summary": "No visit records available for analysis.",
            "past_treatments": [],
            "medicines": [],
            "reactions": [],
            "missed_followups": [],
            "trends": [],
            "missing_information": ["No visits recorded yet."],
            "contradictions": [],
        }

    # Check for GEMINI_API_KEY or GOOGLE_API_KEY dynamically from environment
    gemini_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    is_key_configured = (
        bool(gemini_key) and 
        gemini_key != "your_gemini_api_key_here" and
        not gemini_key.startswith("your_")
    )

    if is_key_configured:
        patient_context = build_patient_context(patient_name, health_id, visits)
        try:
            from google import genai

            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=f"{SYSTEM_PROMPT}\n\n{patient_context}",
            )

            response_text = response.text.strip()

            # Clean markdown code fences if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                response_text = "\n".join(lines)

            result = json.loads(response_text)

            expected_keys = [
                "summary", "past_treatments", "medicines", "reactions",
                "missed_followups", "trends", "missing_information", "contradictions"
            ]
            for key in expected_keys:
                if key not in result:
                    result[key] = [] if key != "summary" else ""

            return result

        except Exception as e:
            # Fall back to clinical rule engine
            print(f"[AI Service] Gemini call failed ({str(e)}). Using clinical rules fallback.")

    # Clinical rules engine fallback
    return _clinical_rules_analyzer(patient_name, health_id, visits)
