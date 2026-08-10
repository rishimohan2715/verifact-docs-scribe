# Verifact

A local-first clinical documentation tool: record a consultation, get a diarized
transcript, an auto-drafted discharge summary / OPD note, ICD-10 and SNOMED CT
codes, prescriptions, and evidence-grounded clinical risk alerts — all
generated on-device, with the audio and every derived record staying on your
machine.

## Architecture

**Frontend** — TanStack Start + React + Tailwind, `localhost:8080`.

**Backend** — FastAPI (`backend/main.py`), `localhost:8000`. On each recording:

1. `faster-whisper` transcribes the audio.
2. A speaker-attribution heuristic diarizes it into DOCTOR/PATIENT turns.
3. Presidio redacts PII before the transcript is handed to the LLM step.
4. Ollama drafts the note plus risk alerts and differentials in one
   schema-constrained call (falls back to a generic extractive summarizer,
   never a diagnosis guess, if Ollama isn't running — see
   [Note generation](#note-generation--ai-analysis) below).
5. Local datasets auto-match ICD-10 codes, SNOMED CT concepts, and
   prescriptions.
6. Every risk-alert/differential evidence quote is verified as an actual
   substring of the transcript before being shown to the clinician.
7. Everything is persisted to SQLite (`backend/data/verifact_local.db`).

The frontend only ever talks to `localhost:8000` — nothing here calls out to
the internet.

## Setup

### 1. Backend (Python)

```sh
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**ffmpeg** — used to normalize uploaded audio to 16kHz mono PCM before Whisper
sees it. Not strictly required (transcription falls back to the raw file if
it's missing), but non-WebM uploads are more reliable with it installed:

```sh
brew install ffmpeg        # macOS
apt-get install ffmpeg     # Debian/Ubuntu
```

**Ollama** — used for note drafting, risk-alert detection, and differential
diagnosis. Optional: if it's not running, or its response doesn't validate,
`services/llm.py` transparently falls back to a generic extractive summarizer
instead of failing — see [Note generation & AI analysis](#note-generation--ai-analysis).

```sh
brew install ollama
ollama serve
ollama pull llama3.2:3b   # or: medgemma, llama3, llama3.1, mistral
```

`_get_available_ollama_model()` in `services/llm.py` checks `localhost:11434`
for whichever of those models is installed, preferring `medgemma` first. Set
`OLLAMA_MODEL` to override the fallback name if none of those are found. Set
`OLLAMA_TIMEOUT_SECONDS` (default `90`) if generation needs longer on your
hardware — a combined note+risk+differential response from a 3B model
typically takes 10-25s on CPU.

**Whisper models** — `faster-whisper` downloads model weights on first use and
caches them in RAM for the life of the process (`get_cached_whisper_model` in
`services/transcription.py`). The frontend's model picker offers `base`,
`small`, `medium`, and `large-v3`; larger models are slower but materially more
accurate on medical vocabulary.

Run the backend:

```sh
uvicorn --app-dir backend main:app --reload --port 8000
# or, from the repo root:
npm run dev:backend
```

On startup it creates `backend/data/verifact_local.db` (SQLite) and
`backend/storage/audio/` (recordings) if they don't already exist. Both are
gitignored — they hold real patient data and must never leave the machine.

### 2. Frontend (Node)

```sh
npm install
npm run dev
```

### 3. Both at once

```sh
npm run dev:all     # runs start-local.sh: backend with --reload, then the frontend
```

## Backend API

All routes are under `http://localhost:8000/api`.

| Method | Path                                  | Purpose                                              |
| ------ | -------------------------------------- | ----------------------------------------------------- |
| GET    | `/health`                              | Backend/DB status                                     |
| POST   | `/transcribe`                          | Upload audio → transcript + note + codes + risk       |
| POST   | `/generate-random-case`                | Synthetic demo consultation, no audio needed          |
| GET    | `/consultations`                       | List all consultations                                |
| GET    | `/consultations/{id}`                  | Full record: transcript, note, codes, rx, risk         |
| PUT    | `/consultations/{id}`                  | Persist edits (sections, transcript, codes, rx)        |
| POST   | `/consultations/{id}/sign`             | Lock a note as signed                                  |
| GET    | `/consultations/{id}/audit-trail`      | Edit history for a consultation                        |
| POST   | `/generate-note`                       | Re-run note/risk/differential generation ("Regenerate Report") |
| GET    | `/icd10?q=`                             | Search the local ICD-10 dataset                        |
| GET    | `/snomed?q=`                            | Search the local SNOMED CT dataset                      |
| GET    | `/medications?q=`                      | Search the local medications dataset                   |

## Note generation & AI analysis

`services/llm.generate_clinical_note()` asks Ollama for the note sections,
risk alerts, and differential diagnoses **in one call**, constrained to an
explicit JSON Schema passed as Ollama's `format` parameter (not just the
string `"json"`) — this forces the response into the right shape at the
decoding level instead of hoping a 3B-parameter model follows prose
instructions. Even so, every `evidenceQuote`/`evidence` string returned is
checked against the actual transcript (`_verify_quote`, whitespace/case
normalized) before being trusted: **anything that isn't a real substring of
the transcript is dropped**, never shown to the clinician. This is the fix
for a real failure mode — smaller local models will occasionally invent a
plausible-sounding quote, and the old version had no way to catch that.

If Ollama is unreachable, its response fails schema validation, or it echoes
the field descriptions back as if they were the answer (also seen in
practice, and checked for explicitly — `_looks_like_schema_echo`),
`_extractive_fallback_note_generator()` takes over: it builds the HPI from
the transcript's own sentences (patient turns, by default-including anything
that isn't a question or clearly clinician-phrased) rather than matching
against a fixed disease list, and explicitly states that diagnosis/treatment/
follow-up were **not generated** rather than guessing. The note's
`generationStatus` (`success` | `extracted_fallback` | `demo_fast_extract`)
is persisted and shown as a banner in the review screen whenever a note
wasn't LLM-generated — clinicians should not assume a fallback note is
equivalent to one the model actually drafted.

`services/clinical_rules.py` and `services/differential.py` are the
rule-based fallback for risk alerts / differentials specifically (used only
when the LLM path above didn't run) — keyword-triggered, but each
`evidenceQuote` is the actual matching sentence pulled from the real
transcript (`services/text_extraction.find_sentences_containing`), never a
hardcoded string.

## SNOMED CT

`backend/data/snomed_codes.json` is a curated subset (~34 concepts) spanning
common primary/urgent-care presentations, each with a `conceptId`,
`preferredTerm`, and cross-referenced `icd10Map` — not the full SNOMED CT
International release (350k+ concepts, distributed as licensed RF2 files
under an IHTSDO Affiliate Agreement, which doesn't fit this app's
load-a-JSON-and-cache architecture). Concept IDs were verified against
public SNOMED CT references while building this dataset rather than guessed;
still, treat it as best-effort for a local/personal tool, not a
production-grade terminology binding — verify against an official
terminology server before any real interoperability or billing use.
`auto_match_snomed_codes()` in `services/medical_knowledge.py` matches it the
same way ICD-10 is matched (keyword-scored, top 5).

## Speaker diarization

`faster-whisper`'s VAD-filtered segments come back **contiguous** — every
inter-segment silence gap is `0.0s` on real recordings, so there's no timing
signal for "who spoke when." `services/transcription._infer_speaker` instead
uses the linguistic shape of a clinical consultation, checked in this order:

1. Ends in `?` → the clinician is asking, label `DOCTOR`.
2. Contains first-person symptom language (`"I've been..."`, `"my chest..."`)
   → the patient is answering, label `PATIENT`.
3. Immediately follows a question → it's the answer, label `PATIENT`.
4. Contains a clinician phrase (`"tell me"`, `"let me"`, `"examination"`, …)
   → label `DOCTOR`.
5. No cue at all → keep the current speaker (handles a sentence Whisper split
   across two segments).

The "Doctor/Patient Speaks First" dropdown only seeds the very first,
otherwise-ambiguous segment; every segment after that is decided by the rules
above. On the real recording used to build this heuristic, it reconstructs
19/19 turns correctly — see `backend/tests/test_transcription.py`.

## Database migrations

`backend/database.py` calls `Base.metadata.create_all()` on startup, which
only creates tables that don't exist yet — **it never adds a column to a
table that already exists.** Adding a field to a model in `models.py` (e.g.
`ClinicalNote.icd10_json`) without also handling this will make every insert
against an existing `verifact_local.db` fail with `OperationalError: table X
has no column named Y`. This actually happened during development and was
masked by the frontend fabricating a note instead of surfacing the 500.

`ensure_schema_current()` (also in `database.py`, called right after
`create_all()`) fixes this going forward: it diffs each model's columns
against what's actually in the SQLite file and backfills anything missing
with `ALTER TABLE ... ADD COLUMN`. It's conservative — non-nullable columns
with no default are logged and skipped rather than guessed at, since SQLite
can't add a `NOT NULL` column with no default to a non-empty table. If you
see that warning in the logs, the column needs a real migration, not an
auto-fix.

This does **not** replace a real migration tool for anything beyond additive,
nullable columns. If the project outgrows that, reach for Alembic.

## Testing

```sh
cd backend
venv/bin/pytest          # 58 tests, no model weights, GPU, or Ollama required
```

The suite mocks external calls at the boundary (`faster-whisper`'s model,
Ollama's HTTP call), so it runs in well under a second and never touches
`backend/data/verifact_local.db`. Beyond the diarization/migration/filename
tests described above, it covers:

- `test_llm_ollama.py` — `generate_clinical_note` against a mocked Ollama
  response: success path, timeout/malformed-JSON fallback, and the
  quote-verification behavior (an unverifiable evidence quote is dropped
  even when the rest of the response is well-formed).
- `test_extractive_fallback_generic.py` — regression test for the original
  bug report: a real, non-emergency transcript (abdominal cramping,
  bloating, diarrhea) must produce a real narrative, never a raw transcript
  dump, and must not guess a diagnosis.
- `test_quote_verification.py` — unit tests for the substring-verification
  helpers themselves.
- `test_clinical_rules_evidence_extraction.py` — confirms the rule-based
  fallback's evidence is a real transcript sentence, not a canned string.
- `test_snomed_matching.py` — SNOMED dataset loading and keyword matching.
- `test_medical_knowledge.py` — prescription suggestion relevance (a
  regression test for an IBS case that used to also suggest Aspirin,
  Nitroglycerin, and an SSRI).

There's no frontend test runner configured yet — `npm run lint` (ESLint +
Prettier) is the only current guard on `src/`.

## Privacy

Recordings and their derived transcripts/notes are real patient data. They
live only in `backend/storage/audio/` and `backend/data/verifact_local.db`,
both gitignored. Don't add either to version control, and don't paste
consultation content into external tools.
