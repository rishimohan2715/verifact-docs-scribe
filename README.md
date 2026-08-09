# Verifact

A local-first clinical documentation tool: record a consultation, get a diarized
transcript, an auto-drafted discharge summary / OPD note, ICD-10 codes,
prescriptions, and clinical risk alerts — all generated on-device, with the
audio and every derived record staying on your machine.

## Architecture

**Frontend** — TanStack Start + React + Tailwind, `localhost:8080`.

**Backend** — FastAPI (`backend/main.py`), `localhost:8000`. On each recording:

1. `faster-whisper` transcribes the audio.
2. A speaker-attribution heuristic diarizes it into DOCTOR/PATIENT turns.
3. Presidio redacts PII before the transcript is handed to the LLM step.
4. Ollama drafts the note sections (falls back to a fast local NLP extractor
   if Ollama isn't running).
5. Local datasets auto-match ICD-10 codes and prescriptions.
6. Rule-based clinical risk checks run over the transcript.
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

**Ollama** — used for note drafting. Optional: if it's not running, or none of
the models below are pulled, `services/llm.py` transparently falls back to a
fast local NLP extractor (`_dynamic_nlp_note_generator`) instead of failing.

```sh
brew install ollama
ollama serve
ollama pull llama3.2:3b   # or: medgemma, llama3, llama3.1, mistral
```

`_get_available_ollama_model()` in `services/llm.py` checks `localhost:11434`
for whichever of those models is installed, preferring `medgemma` first. Set
`OLLAMA_MODEL` to override the fallback name if none of those are found.

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
| GET    | `/icd10?q=`                            | Search the local ICD-10 dataset                        |
| GET    | `/medications?q=`                      | Search the local medications dataset                   |

> **Known gap:** the "Regenerate Report" button in the note review screen
> calls `POST /api/generate-note`, which doesn't exist yet in `main.py` — it
> currently 404s and the UI silently swallows that into a misleading success
> toast. Worth fixing in a follow-up.

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
venv/bin/pytest          # 23 tests, no model weights or GPU required
```

The suite mocks `faster-whisper` entirely (`get_cached_whisper_model` is
patched with a fake model), so it runs in well under a second and never
touches `backend/data/verifact_local.db`. It covers:

- `test_speaker_attribution.py` — the diarization heuristic, rule by rule.
- `test_transcription.py` — `transcribe_audio` end to end against mocked
  segments, including a regression test built from a real recording where
  every segment used to collapse onto a single speaker.
- `test_schema_migration.py` — `ensure_schema_current()` against a
  deliberately stale SQLite file, reproducing the exact `OperationalError`
  incident above.
- `test_audio_filename.py` — filename uniqueness; two uploads that used to
  land in the same wall-clock second would silently overwrite each other's
  saved audio.

There's no frontend test runner configured yet — `npm run lint` (ESLint +
Prettier) is the only current guard on `src/`.

## Privacy

Recordings and their derived transcripts/notes are real patient data. They
live only in `backend/storage/audio/` and `backend/data/verifact_local.db`,
both gitignored. Don't add either to version control, and don't paste
consultation content into external tools.
