"""SQLite database storage and version management for events and documents."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from docgen.models import EventRecord

Base = declarative_base()


def utc_now() -> datetime:
    """Return current naive UTC datetime for SQLAlchemy/SQLite compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EventModel(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    event_name = Column(String, nullable=True)
    record_type = Column(String, default="event")
    data_json = Column(Text, nullable=False)


class DocumentVersionModel(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=False)
    template_id = Column(String, nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=utc_now)
    docx_path = Column(String, nullable=False)
    pdf_path = Column(String, nullable=True)
    snapshot_json = Column(Text, nullable=False)
    diff_summary = Column(Text, nullable=True)
    manually_edited = Column(Integer, default=0)


class NumberingCounterModel(Base):
    __tablename__ = "numbering_counters"

    series = Column(String, primary_key=True)
    last_seq = Column(Integer, default=0)


class Database:
    def __init__(self, db_path: str | Path = "data/docgen.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_event(self, event: EventRecord) -> str:
        session = self.Session()
        try:
            name = event.event_name.value if event.event_name else "Unnamed Event"
            rec_type = event.record_type.value if event.record_type else "event"
            data_str = event.model_dump_json()

            existing = session.query(EventModel).filter_by(id=event.id).first()
            if existing:
                existing.event_name = name
                existing.record_type = rec_type
                existing.data_json = data_str
                existing.updated_at = utc_now()
            else:
                record = EventModel(
                    id=event.id,
                    event_name=name,
                    record_type=rec_type,
                    data_json=data_str,
                )
                session.add(record)
            session.commit()
            return event.id
        finally:
            session.close()

    def get_event(self, event_id: str) -> Optional[EventRecord]:
        session = self.Session()
        try:
            record = session.query(EventModel).filter_by(id=event_id).first()
            if not record:
                return None
            data = json.loads(record.data_json)
            return EventRecord.model_validate(data)
        finally:
            session.close()

    def list_events(self) -> list[dict[str, Any]]:
        session = self.Session()
        try:
            records = session.query(EventModel).order_by(EventModel.updated_at.desc()).all()
            return [
                {
                    "id": r.id,
                    "event_name": r.event_name,
                    "record_type": r.record_type,
                    "updated_at": r.updated_at,
                }
                for r in records
            ]
        finally:
            session.close()

    def save_version(
        self,
        event_id: str,
        template_id: str,
        version: int,
        docx_path: str,
        pdf_path: Optional[str],
        snapshot: dict[str, Any],
        diff_summary: str = "",
        manually_edited: bool = False,
    ) -> int:
        session = self.Session()
        try:
            v_record = DocumentVersionModel(
                event_id=event_id,
                template_id=template_id,
                version=version,
                docx_path=docx_path,
                pdf_path=pdf_path,
                snapshot_json=json.dumps(snapshot, default=str),
                diff_summary=diff_summary,
                manually_edited=1 if manually_edited else 0,
            )
            session.add(v_record)
            session.commit()
            return v_record.id
        finally:
            session.close()

    def get_versions(self, event_id: str, template_id: Optional[str] = None) -> list[dict[str, Any]]:
        session = self.Session()
        try:
            query = session.query(DocumentVersionModel).filter_by(event_id=event_id)
            if template_id:
                query = query.filter_by(template_id=template_id)
            records = query.order_by(DocumentVersionModel.version.desc()).all()
            return [
                {
                    "id": r.id,
                    "event_id": r.event_id,
                    "template_id": r.template_id,
                    "version": r.version,
                    "created_at": r.created_at,
                    "docx_path": r.docx_path,
                    "pdf_path": r.pdf_path,
                    "diff_summary": r.diff_summary,
                    "manually_edited": bool(r.manually_edited),
                }
                for r in records
            ]
        finally:
            session.close()

    def get_next_sequence(self, series: str, initial: int = 0) -> int:
        session = self.Session()
        try:
            counter = session.query(NumberingCounterModel).filter_by(series=series).first()
            if not counter:
                counter = NumberingCounterModel(series=series, last_seq=initial + 1)
                session.add(counter)
            else:
                counter.last_seq += 1
            session.commit()
            return counter.last_seq
        finally:
            session.close()
