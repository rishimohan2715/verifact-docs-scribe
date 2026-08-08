import { useSyncExternalStore } from "react";

export type NoteStatus = "draft" | "pending" | "signed";
export type NoteType = "Discharge Summary" | "OPD Note";

export interface TranscriptLine {
  speaker: "DOCTOR" | "PATIENT";
  time: string; // mm:ss
  text: string;
  start?: number;
  end?: number;
}

export interface NoteSections {
  chiefComplaint: string;
  hpi: string;
  examination: string;
  diagnosis: string;
  treatment: string;
  followUp: string;
}

export interface ICD10Code {
  code: string;
  title: string;
  category: string;
}

export interface Prescription {
  id?: string;
  name: string;
  brand?: string;
  dosage: string;
  frequency: string;
  route: string;
  duration: string;
  indication?: string;
}

export interface Note {
  id: string;
  patientName: string;
  mrn: string;
  consultTime: string; // ISO
  type: NoteType;
  status: NoteStatus;
  sections: NoteSections;
  icd10Codes: ICD10Code[];
  prescriptions: Prescription[];
  editedFields: Partial<Record<keyof NoteSections, boolean>>;
  editsCount: number;
  transcript: TranscriptLine[];
  reviewSeconds?: number;
  signedAt?: string;
}

type State = { notes: Note[] };

const listeners = new Set<() => void>();
let state: State = { notes: [] };

function emit() {
  listeners.forEach((l) => l());
}

export function setState(fn: (s: State) => State) {
  state = fn(state);
  emit();
}

export function getState() {
  return state;
}

export function useStore<T>(selector: (s: State) => T): T {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => selector(state),
    () => selector(state),
  );
}

export function upsertNote(note: Note) {
  setState((s) => {
    const idx = s.notes.findIndex((n) => n.id === note.id);
    const next = [...s.notes];
    if (idx >= 0) next[idx] = note;
    else next.unshift(note);
    return { notes: next };
  });
}

export function updateNote(id: string, patch: (n: Note) => Note) {
  setState((s) => ({
    notes: s.notes.map((n) => (n.id === id ? patch(n) : n)),
  }));
}

export function editSection(id: string, key: keyof NoteSections, value: string) {
  updateNote(id, (n) => {
    if (n.sections[key] === value) return n;
    const wasEdited = n.editedFields[key];
    const updatedNote = {
      ...n,
      sections: { ...n.sections, [key]: value },
      editedFields: { ...n.editedFields, [key]: true },
      editsCount: wasEdited ? n.editsCount : n.editsCount + 1,
    };
    
    saveConsultationSectionToBackend(id, updatedNote.sections);
    return updatedNote;
  });
}

export function addIcd10Code(id: string, code: ICD10Code) {
  updateNote(id, (n) => {
    if (n.icd10Codes.some((c) => c.code === code.code)) return n;
    const next = [...n.icd10Codes, code];
    const updated = { ...n, icd10Codes: next, editsCount: n.editsCount + 1 };
    saveICD10ToBackend(id, next);
    return updated;
  });
}

export function removeIcd10Code(id: string, codeStr: string) {
  updateNote(id, (n) => {
    const next = n.icd10Codes.filter((c) => c.code !== codeStr);
    const updated = { ...n, icd10Codes: next };
    saveICD10ToBackend(id, next);
    return updated;
  });
}

export function addPrescription(id: string, rx: Prescription) {
  updateNote(id, (n) => {
    const rxWithId = { ...rx, id: rx.id || `rx-${Date.now()}` };
    const next = [...n.prescriptions, rxWithId];
    const updated = { ...n, prescriptions: next, editsCount: n.editsCount + 1 };
    savePrescriptionsToBackend(id, next);
    return updated;
  });
}

export function removePrescription(id: string, rxId: string) {
  updateNote(id, (n) => {
    const next = n.prescriptions.filter((p, i) => (p.id || `rx-${i}`) !== rxId);
    const updated = { ...n, prescriptions: next };
    savePrescriptionsToBackend(id, next);
    return updated;
  });
}

export function editTranscriptLine(id: string, index: number, speaker: "DOCTOR" | "PATIENT", text: string) {
  updateNote(id, (n) => {
    const updatedTranscript = [...n.transcript];
    updatedTranscript[index] = { ...updatedTranscript[index], speaker, text };
    const updatedNote = { ...n, transcript: updatedTranscript };
    saveTranscriptToBackend(id, updatedTranscript);
    return updatedNote;
  });
}

export async function signNote(id: string, reviewSeconds: number) {
  updateNote(id, (n) => ({
    ...n,
    status: "signed",
    reviewSeconds,
    signedAt: new Date().toISOString(),
  }));

  try {
    await fetch(`http://localhost:8000/api/consultations/${id}/sign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_seconds: reviewSeconds }),
    });
  } catch (err) {
    console.warn("Local backend sync offline, saved in local state.", err);
  }
}

// ─── Local Backend Integration ───────────────────────────────────────────────

const BACKEND_URL = "http://localhost:8000/api";

export async function fetchLocalConsultations() {
  try {
    const res = await fetch(`${BACKEND_URL}/consultations`);
    if (!res.ok) return;
    const data = await res.json();
    for (const item of data) {
      await fetchAndUpsertConsultation(item.id);
    }
  } catch (err) {
    console.warn("Local FastAPI backend unreachable. Using local state.", err);
  }
}

export async function fetchAndUpsertConsultation(consultationId: string) {
  try {
    const res = await fetch(`${BACKEND_URL}/consultations/${consultationId}`);
    if (!res.ok) return;
    const data = await res.json();

    const noteData: Note = {
      id: data.id,
      patientName: data.patientName ?? "Unknown Patient",
      mrn: data.mrn ?? "UNKNOWN",
      consultTime: data.consultTime ?? new Date().toISOString(),
      type: (data.type as NoteType) ?? "Discharge Summary",
      status: (data.status as NoteStatus) ?? "pending",
      sections: data.sections ?? {
        chiefComplaint: "", hpi: "", examination: "", diagnosis: "", treatment: "", followUp: ""
      },
      icd10Codes: data.icd10Codes ?? [
        { code: "R10.9", title: "Unspecified abdominal pain", category: "Gastrointestinal" },
        { code: "R11.2", title: "Nausea with vomiting, unspecified", category: "Gastrointestinal" },
        { code: "G51.0", title: "Bell's palsy / Facial nerve paralysis", category: "Neurological" }
      ],
      prescriptions: data.prescriptions ?? [
        { name: "Ondansetron", brand: "Vomikind", dosage: "4 mg", frequency: "TDS", route: "Oral", duration: "5 days" },
        { name: "Pantoprazole", brand: "Pan 40", dosage: "40 mg", frequency: "OD (Before meals)", route: "Oral", duration: "14 days" }
      ],
      editedFields: {},
      editsCount: data.editsCount ?? 0,
      transcript: data.transcript ?? [],
      reviewSeconds: data.reviewSeconds ?? 0,
      signedAt: data.signedAt,
    };

    upsertNote(noteData);
    return noteData;
  } catch (err) {
    console.error("Failed to fetch consultation from local backend:", err);
  }
}

async function saveConsultationSectionToBackend(id: string, sections: NoteSections) {
  try {
    await fetch(`${BACKEND_URL}/consultations/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sections }),
    });
  } catch (err) {
    console.warn("Failed to persist section edit to local backend", err);
  }
}

async function saveICD10ToBackend(id: string, icd10_codes: ICD10Code[]) {
  try {
    await fetch(`${BACKEND_URL}/consultations/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ icd10_codes }),
    });
  } catch (err) {
    console.warn("Failed to persist ICD-10 codes to local backend", err);
  }
}

async function savePrescriptionsToBackend(id: string, prescriptions: Prescription[]) {
  try {
    await fetch(`${BACKEND_URL}/consultations/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prescriptions }),
    });
  } catch (err) {
    console.warn("Failed to persist prescriptions to local backend", err);
  }
}

async function saveTranscriptToBackend(id: string, transcript: TranscriptLine[]) {
  try {
    await fetch(`${BACKEND_URL}/consultations/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript }),
    });
  } catch (err) {
    console.warn("Failed to persist transcript edit to local backend", err);
  }
}
