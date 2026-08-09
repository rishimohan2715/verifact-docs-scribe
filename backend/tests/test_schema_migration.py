"""
Tests for database.ensure_schema_current().

Context (a real incident this reproduces): models.py gained
ClinicalNote.icd10_json and .prescriptions_json, but Base.metadata.create_all()
only creates missing *tables* — it never adds a column to a table that already
exists. Every insert against the pre-existing database then failed with
sqlalchemy.exc.OperationalError: "table clinical_notes has no column named
icd10_json", and the frontend's error handling (at the time) papered over the
500 with a fabricated note. ensure_schema_current() backfills such columns on
startup so an old database file stays compatible with newer models.py code.

Each test points database.engine / database.Base at a throwaway SQLite file
and a disposable declarative base, so the real backend/data/verifact_local.db
is never touched.
"""
import sqlite3

import pytest
from sqlalchemy import Column, String, Text, Integer, create_engine
from sqlalchemy.orm import declarative_base

import database


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Points database.engine/Base at a fresh temp SQLite file for one test."""
    db_path = tmp_path / "test.db"
    test_engine = create_engine(f"sqlite:///{db_path}")
    monkeypatch.setattr(database, "engine", test_engine)
    yield db_path, test_engine


def _columns(db_path, table_name):
    conn = sqlite3.connect(db_path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    finally:
        conn.close()


def test_missing_nullable_column_is_backfilled(isolated_db, monkeypatch):
    db_path, test_engine = isolated_db

    OldBase = declarative_base()

    class ClinicalNoteV1(OldBase):
        __tablename__ = "clinical_notes"
        id = Column(String, primary_key=True)
        sections_json = Column(Text, nullable=False, default="{}")

    OldBase.metadata.create_all(bind=test_engine)
    assert _columns(db_path, "clinical_notes") == {"id", "sections_json"}

    NewBase = declarative_base()

    class ClinicalNoteV2(NewBase):
        __tablename__ = "clinical_notes"
        id = Column(String, primary_key=True)
        sections_json = Column(Text, nullable=False, default="{}")
        icd10_json = Column(Text, nullable=True)
        prescriptions_json = Column(Text, nullable=True)

    monkeypatch.setattr(database, "Base", NewBase)
    database.ensure_schema_current()

    assert _columns(db_path, "clinical_notes") == {
        "id", "sections_json", "icd10_json", "prescriptions_json",
    }


def test_backfilled_column_actually_accepts_inserts(isolated_db, monkeypatch):
    """
    Column presence alone doesn't prove the fix — this is the same statement
    shape that originally raised OperationalError in production.
    """
    db_path, test_engine = isolated_db

    OldBase = declarative_base()

    class ClinicalNoteV1(OldBase):
        __tablename__ = "clinical_notes"
        id = Column(String, primary_key=True)

    OldBase.metadata.create_all(bind=test_engine)

    NewBase = declarative_base()

    class ClinicalNoteV2(NewBase):
        __tablename__ = "clinical_notes"
        id = Column(String, primary_key=True)
        icd10_json = Column(Text, nullable=True)

    monkeypatch.setattr(database, "Base", NewBase)
    database.ensure_schema_current()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO clinical_notes (id, icd10_json) VALUES (?, ?)",
            ("note-1", '[{"code": "J45.901"}]'),
        )
        conn.commit()
        row = conn.execute("SELECT icd10_json FROM clinical_notes WHERE id = ?", ("note-1",)).fetchone()
    finally:
        conn.close()

    assert row[0] == '[{"code": "J45.901"}]'


def test_missing_required_column_without_default_is_left_alone(isolated_db, monkeypatch):
    """
    SQLite can't ALTER TABLE ADD COLUMN with a NOT NULL constraint and no default
    against a non-empty table. ensure_schema_current must skip these rather than
    crash the whole startup migration, and leave the column genuinely absent so
    the gap is visible (a warning is logged) instead of silently ignored.
    """
    db_path, test_engine = isolated_db

    OldBase = declarative_base()

    class ThingV1(OldBase):
        __tablename__ = "things"
        id = Column(String, primary_key=True)

    OldBase.metadata.create_all(bind=test_engine)

    NewBase = declarative_base()

    class ThingV2(NewBase):
        __tablename__ = "things"
        id = Column(String, primary_key=True)
        required_count = Column(Integer, nullable=False)  # no default, no server_default

    monkeypatch.setattr(database, "Base", NewBase)
    database.ensure_schema_current()  # must not raise

    assert "required_count" not in _columns(db_path, "things")


def test_brand_new_table_is_left_for_create_all_not_altered(isolated_db, monkeypatch):
    """A table entirely absent from the old DB is create_all's job, not ALTER TABLE's."""
    db_path, test_engine = isolated_db

    OldBase = declarative_base()

    class ExistingV1(OldBase):
        __tablename__ = "existing_table"
        id = Column(String, primary_key=True)

    OldBase.metadata.create_all(bind=test_engine)

    NewBase = declarative_base()

    class ExistingV2(NewBase):
        __tablename__ = "existing_table"
        id = Column(String, primary_key=True)

    class BrandNewTable(NewBase):
        __tablename__ = "brand_new_table"
        id = Column(String, primary_key=True)

    monkeypatch.setattr(database, "Base", NewBase)
    database.ensure_schema_current()  # must not raise trying to ALTER a table that doesn't exist yet

    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert "brand_new_table" not in tables


def test_running_twice_is_idempotent(isolated_db, monkeypatch):
    db_path, test_engine = isolated_db

    OldBase = declarative_base()

    class ClinicalNoteV1(OldBase):
        __tablename__ = "clinical_notes"
        id = Column(String, primary_key=True)

    OldBase.metadata.create_all(bind=test_engine)

    NewBase = declarative_base()

    class ClinicalNoteV2(NewBase):
        __tablename__ = "clinical_notes"
        id = Column(String, primary_key=True)
        icd10_json = Column(Text, nullable=True)

    monkeypatch.setattr(database, "Base", NewBase)
    database.ensure_schema_current()
    database.ensure_schema_current()  # must not raise "duplicate column name"

    assert _columns(db_path, "clinical_notes") == {"id", "icd10_json"}
