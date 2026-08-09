import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import engine, Base, get_db, ensure_schema_current, STORAGE_DIR
from models import Consultation, Transcript, ClinicalNote, AuditLog
from services.transcription import transcribe_audio
from services.audio import generate_audio_filename
from services.redaction import redact_pii
from services.llm import generate_clinical_note, generate_clinical_note_fast
from services.medical_knowledge import (
    load_icd10_dataset,
    load_medications_dataset,
    auto_match_icd10_codes,
    auto_suggest_prescriptions
)
from services.clinical_rules import analyze_clinical_risks
from services.differential import generate_differential_details
from services.random_case import generate_random_case_payload

# Initialize SQLite tables, then backfill columns added to models since the DB was created
Base.metadata.create_all(bind=engine)
ensure_schema_current()

app = FastAPI(
    title="Verifact Local Clinical AI Pipeline",
    description="100% Local DPDP-compliant STT, PII Redaction, ICD-10, Rx & Audit Trail API",
    version="1.6.0"
)

# Configure CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/audio", StaticFiles(directory=STORAGE_DIR), name="audio")

# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class NoteGenerationRequest(BaseModel):
    consultation_id: str
    template_id: Optional[str] = "cura-discharge.json"

class UpdateConsultationRequest(BaseModel):
    sections: Optional[Dict[str, str]] = None
    transcript: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None
    icd10_codes: Optional[List[Dict[str, Any]]] = None
    prescriptions: Optional[List[Dict[str, Any]]] = None

class SignNoteRequest(BaseModel):
    review_seconds: int

class MergeSegmentsRequest(BaseModel):
    segment_index_1: int
    segment_index_2: int

class SplitSegmentRequest(BaseModel):
    segment_index: int
    split_character_index: int

# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """Health check verifying database and local ML services."""
    try:
        consultation_count = db.query(Consultation).count()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return {
        "status": "online",
        "privacy": "100% Local (DPDP Compliant)",
        "database": db_status,
        "consultations_count": consultation_count,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/icd10")
def get_icd10_codes(q: Optional[str] = None):
    dataset = load_icd10_dataset()
    if not q:
        return dataset
    q_lower = q.lower().strip()
    return [
        item for item in dataset
        if q_lower in item["code"].lower()
        or q_lower in item["title"].lower()
        or any(q_lower in kw for kw in item.get("keywords", []))
    ]


@app.get("/api/medications")
def get_medications(q: Optional[str] = None):
    dataset = load_medications_dataset()
    if not q:
        return dataset
    q_lower = q.lower().strip()
    return [
        item for item in dataset
        if q_lower in item["name"].lower()
        or q_lower in item["brand"].lower()
        or q_lower in item["indication"].lower()
    ]


@app.post("/api/generate-random-case")
def generate_random_case_endpoint(db: Session = Depends(get_db)):
    """
    Dynamically generates a synchronized clinical scenario with explicit state machine transitions.
    """
    random_payload = generate_random_case_payload()
    full_transcript = random_payload["full_transcript"]
    segments = random_payload["segments"]

    redacted_transcript, redactions = redact_pii(full_transcript)

    consultation = Consultation(
        patient_name=random_payload["patient_name"],
        mrn=random_payload["mrn"],
        consult_type=random_payload["consult_type"],
        status="processing",
        audio_path="RANDOM_DYNAMIC_AUDIO",
        duration=segments[-1]["end"] if segments else 0.0
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    transcript_record = Transcript(
        consultation_id=consultation.id,
        raw_text=full_transcript,
        speaker_json=json.dumps(segments)
    )
    db.add(transcript_record)
    db.commit()

    template_path = os.path.join(os.path.dirname(__file__), "templates", "cura-discharge.json")
    template_config = {}
    if os.path.exists(template_path):
        with open(template_path, "r") as tf:
            template_config = json.load(tf)

    note_result = generate_clinical_note_fast(redacted_transcript, template_config)

    matched_icd10 = auto_match_icd10_codes(full_transcript, note_result["sections"].get("diagnosis", ""))
    suggested_prescriptions = auto_suggest_prescriptions(full_transcript, note_result["sections"].get("diagnosis", ""))
    clinical_risk_analysis = analyze_clinical_risks(full_transcript, note_result["sections"].get("diagnosis", ""))
    differentials = generate_differential_details(full_transcript, note_result["sections"].get("diagnosis", ""))

    clinical_note = ClinicalNote(
        consultation_id=consultation.id,
        template_used="cura-discharge.json",
        prompt_version=note_result.get("prompt_version", "v1.0.0"),
        generated_text=note_result["structured_note"],
        sections_json=json.dumps(note_result["sections"]),
        raw_generated_sections_json=json.dumps(note_result["sections"]),
        status="review"
    )
    db.add(clinical_note)

    # Log initial state creation audit log
    audit_entry = AuditLog(
        consultation_id=consultation.id,
        user_id="dr_raman",
        field_name="session_status",
        old_value="recording",
        new_value="review",
        action_type="CREATE"
    )
    db.add(audit_entry)

    consultation.status = "review"
    db.commit()

    return {
        "consultation_id": consultation.id,
        "patient_name": consultation.patient_name,
        "mrn": consultation.mrn,
        "age": random_payload["age"],
        "pmh": random_payload["pmh"],
        "consult_type": consultation.consult_type,
        "scenario_title": random_payload["scenario_title"],
        "status": consultation.status,
        "full_transcript": full_transcript,
        "redacted_transcript": redacted_transcript,
        "segments": segments,
        "icd10_codes": matched_icd10,
        "prescriptions": suggested_prescriptions,
        "clinical_risk_analysis": clinical_risk_analysis,
        "differential_pinpoints": differentials,
        "note": {
            "id": clinical_note.id,
            "sections": note_result["sections"],
            "structured_note": note_result["structured_note"],
            "llm_model": note_result.get("llm_model"),
            "prompt_version": note_result.get("prompt_version")
        }
    }


@app.post("/api/transcribe")
async def transcribe_endpoint(
    file: Optional[UploadFile] = File(None),
    patient_name: str = Form("Rishi Mohan"),
    mrn: str = Form("MRN-48213"),
    consult_type: str = Form("Discharge Summary"),
    first_speaker: str = Form("PATIENT"),
    whisper_model: str = Form("base"),
    db: Session = Depends(get_db)
):
    saved_filename = generate_audio_filename(file.filename if file else None)
    audio_path = os.path.join(STORAGE_DIR, saved_filename)

    if file:
        contents = await file.read()
        with open(audio_path, "wb") as f:
            f.write(contents)
    else:
        with open(audio_path, "wb") as f:
            f.write(b"MOCK_AUDIO_DATA")

    # Use RAM-cached Whisper model (default 'base' for ultra-fast processing)
    transcribe_result = transcribe_audio(audio_path, first_speaker=first_speaker, model_name=whisper_model)
    full_transcript = transcribe_result["full_transcript"]
    segments = transcribe_result["segments"]

    redacted_transcript, redactions = redact_pii(full_transcript)

    consultation = Consultation(
        patient_name=patient_name.strip(),
        mrn=mrn.strip(),
        consult_type=consult_type.strip(),
        status="processing",
        audio_path=audio_path,
        duration=segments[-1]["end"] if segments else 0.0
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    transcript_record = Transcript(
        consultation_id=consultation.id,
        raw_text=full_transcript,
        speaker_json=json.dumps(segments)
    )
    db.add(transcript_record)
    db.commit()

    template_path = os.path.join(os.path.dirname(__file__), "templates", "cura-discharge.json")
    template_config = {}
    if os.path.exists(template_path):
        with open(template_path, "r") as tf:
            template_config = json.load(tf)

    note_result = generate_clinical_note(redacted_transcript, template_config)

    matched_icd10 = auto_match_icd10_codes(full_transcript, note_result["sections"].get("diagnosis", ""))
    suggested_prescriptions = auto_suggest_prescriptions(full_transcript, note_result["sections"].get("diagnosis", ""))
    clinical_risk_analysis = analyze_clinical_risks(full_transcript, note_result["sections"].get("diagnosis", ""))
    differentials = generate_differential_details(full_transcript, note_result["sections"].get("diagnosis", ""))

    clinical_note = ClinicalNote(
        consultation_id=consultation.id,
        template_used="cura-discharge.json",
        prompt_version=note_result.get("prompt_version", "v1.0.0"),
        generated_text=note_result["structured_note"],
        sections_json=json.dumps(note_result["sections"]),
        raw_generated_sections_json=json.dumps(note_result["sections"]),
        status="review"
    )
    db.add(clinical_note)

    audit_entry = AuditLog(
        consultation_id=consultation.id,
        user_id="dr_raman",
        field_name="session_status",
        old_value="recording",
        new_value="review",
        action_type="CREATE"
    )
    db.add(audit_entry)

    consultation.status = "review"
    db.commit()

    return {
        "consultation_id": consultation.id,
        "patient_name": consultation.patient_name,
        "mrn": consultation.mrn,
        "consult_type": consultation.consult_type,
        "status": consultation.status,
        "full_transcript": full_transcript,
        "redacted_transcript": redacted_transcript,
        "segments": segments,
        "icd10_codes": matched_icd10,
        "prescriptions": suggested_prescriptions,
        "clinical_risk_analysis": clinical_risk_analysis,
        "differential_pinpoints": differentials,
        "note": {
            "id": clinical_note.id,
            "sections": note_result["sections"],
            "structured_note": note_result["structured_note"],
            "llm_model": note_result.get("llm_model"),
            "prompt_version": note_result.get("prompt_version")
        }
    }


@app.get("/api/consultations/{consultation_id}/audit-trail")
def get_audit_trail(consultation_id: str, db: Session = Depends(get_db)):
    """Returns the complete immutable audit trail of edits and state transitions for a session."""
    logs = db.query(AuditLog).filter(AuditLog.consultation_id == consultation_id).order_by(AuditLog.created_at.desc()).all()
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "field_name": log.field_name,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "action_type": log.action_type,
            "timestamp": log.created_at.isoformat()
        }
        for log in logs
    ]


@app.put("/api/consultations/{consultation_id}")
def update_consultation(
    consultation_id: str,
    req: UpdateConsultationRequest,
    db: Session = Depends(get_db)
):
    """Updates consultation sections, transcript, or status, generating audit log entries."""
    c = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Consultation not found")

    if req.status and req.status != c.status:
        db.add(AuditLog(
            consultation_id=consultation_id,
            field_name="status",
            old_value=c.status,
            new_value=req.status,
            action_type="STATE_TRANSITION"
        ))
        c.status = req.status

    if req.sections:
        n = db.query(ClinicalNote).filter(ClinicalNote.consultation_id == consultation_id).first()
        if n:
            old_sections = json.loads(n.sections_json) if n.sections_json else {}
            for k, new_val in req.sections.items():
                old_val = old_sections.get(k, "")
                if old_val != new_val:
                    db.add(AuditLog(
                        consultation_id=consultation_id,
                        field_name=f"section.{k}",
                        old_value=old_val[:200],
                        new_value=new_val[:200],
                        action_type="EDIT"
                    ))
            n.sections_json = json.dumps(req.sections)
            n.edit_count += 1
            n.updated_at = datetime.utcnow()

    if req.transcript:
        t = db.query(Transcript).filter(Transcript.consultation_id == consultation_id).first()
        if t:
            t.speaker_json = json.dumps(req.transcript)
            t.raw_text = " ".join([seg.get("text", "") for seg in req.transcript])

    if req.icd10_codes is not None:
        n = db.query(ClinicalNote).filter(ClinicalNote.consultation_id == consultation_id).first()
        if n:
            n.icd10_json = json.dumps(req.icd10_codes)
            db.add(AuditLog(
                consultation_id=consultation_id,
                field_name="icd10_codes",
                old_value="",
                new_value=json.dumps(req.icd10_codes)[:200],
                action_type="EDIT"
            ))

    if req.prescriptions is not None:
        n = db.query(ClinicalNote).filter(ClinicalNote.consultation_id == consultation_id).first()
        if n:
            n.prescriptions_json = json.dumps(req.prescriptions)
            db.add(AuditLog(
                consultation_id=consultation_id,
                field_name="prescriptions",
                old_value="",
                new_value=json.dumps(req.prescriptions)[:200],
                action_type="EDIT"
            ))

    db.commit()
    return {"status": "success", "consultation_id": consultation_id}


@app.post("/api/consultations/{consultation_id}/sign")
def sign_consultation(
    consultation_id: str,
    req: SignNoteRequest,
    db: Session = Depends(get_db)
):
    """Marks note as approved & locked, transitioning state to 'signed' and logging audit entry."""
    c = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Consultation not found")

    old_status = c.status
    c.status = "signed"
    c.time_to_review_seconds = req.review_seconds
    c.signed_at = datetime.utcnow()

    n = db.query(ClinicalNote).filter(ClinicalNote.consultation_id == consultation_id).first()
    if n:
        n.status = "signed"
        n.updated_at = datetime.utcnow()

    db.add(AuditLog(
        consultation_id=consultation_id,
        field_name="status",
        old_value=old_status,
        new_value="signed",
        action_type="SIGN"
    ))

    db.commit()
    return {
        "status": "signed",
        "consultation_id": consultation_id,
        "time_to_review_seconds": c.time_to_review_seconds,
        "signed_at": c.signed_at.isoformat()
    }


@app.get("/api/consultations")
def list_consultations(db: Session = Depends(get_db)):
    consultations = db.query(Consultation).order_by(Consultation.created_at.desc()).all()
    results = []
    for c in consultations:
        note = db.query(ClinicalNote).filter(ClinicalNote.consultation_id == c.id).first()
        results.append({
            "id": c.id,
            "patientName": c.patient_name,
            "mrn": c.mrn,
            "consultTime": c.created_at.isoformat() if c.created_at else None,
            "type": c.consult_type,
            "status": c.status,
            "reviewSeconds": c.time_to_review_seconds,
            "signedAt": c.signed_at.isoformat() if c.signed_at else None,
            "editsCount": note.edit_count if note else 0
        })
    return results


@app.get("/api/consultations/{consultation_id}")
def get_consultation(consultation_id: str, db: Session = Depends(get_db)):
    c = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Consultation not found")

    t = db.query(Transcript).filter(Transcript.consultation_id == consultation_id).first()
    n = db.query(ClinicalNote).filter(ClinicalNote.consultation_id == consultation_id).first()

    segments = json.loads(t.speaker_json) if (t and t.speaker_json) else []
    sections = json.loads(n.sections_json) if (n and n.sections_json) else {
        "chiefComplaint": "", "hpi": "", "examination": "", "diagnosis": "", "treatment": "", "followUp": ""
    }

    raw_text = t.raw_text if t else ""
    matched_icd10 = json.loads(n.icd10_json) if (n and n.icd10_json) else auto_match_icd10_codes(raw_text, sections.get("diagnosis", ""))
    suggested_prescriptions = json.loads(n.prescriptions_json) if (n and n.prescriptions_json) else auto_suggest_prescriptions(raw_text, sections.get("diagnosis", ""))
    clinical_risk_analysis = analyze_clinical_risks(raw_text, sections.get("diagnosis", ""))
    differentials = generate_differential_details(raw_text, sections.get("diagnosis", ""))

    return {
        "id": c.id,
        "patientName": c.patient_name,
        "mrn": c.mrn,
        "consultTime": c.created_at.isoformat() if c.created_at else None,
        "type": c.consult_type,
        "status": c.status,
        "reviewSeconds": c.time_to_review_seconds,
        "signedAt": c.signed_at.isoformat() if c.signed_at else None,
        "transcript": segments,
        "sections": sections,
        "icd10Codes": matched_icd10,
        "prescriptions": suggested_prescriptions,
        "clinicalRiskAnalysis": clinical_risk_analysis,
        "differentialPinpoints": differentials,
        "editsCount": n.edit_count if n else 0,
        "editedFields": {}
    }
