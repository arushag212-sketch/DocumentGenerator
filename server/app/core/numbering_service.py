"""Shared Numbering Allocator Service.

Provides a unified, concurrency-safe numbering allocator for single-document reservations
and atomic batch generation.
- Uses `SELECT ... FOR UPDATE` on PostgreSQL and atomic `UPDATE ... RETURNING` on SQLite.
- Rejects missing academic years without fallback.
- Rejects missing numbering series without auto-provisioning (missing series must be created by an admin).
- Formats reference numbers consistently.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from docgen.numbering import compute_short_year, format_reference_number
from server.app.core.scoped_repo import ScopedRepository
from server.app.models import Club, NumberingSeries, NumberReservation


def resolve_club_and_academic_year(
    db: Session,
    club_id: str,
    academic_year: Optional[str] = None,
    club_code: Optional[str] = None,
) -> tuple[Club, str, str]:
    """Resolve club record, academic year, and club prefix. Rejects if not configured."""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise ValueError(f"Club '{club_id}' not found.")

    ay = academic_year or club.academic_year_default or (club.settings or {}).get("academic_year")
    if not ay or not str(ay).strip():
        raise ValueError(
            f"Academic year is not configured for club '{club.name}'. Please configure academic year default in club settings."
        )

    code = club_code or club.short_name or club.slug.upper()
    return club, str(ay).strip(), code


def allocate_next_sequence(
    db: Session,
    club_id: str,
    series_key: str,
    academic_year: Optional[str] = None,
    club_code: Optional[str] = None,
    format_pattern: Optional[str] = None,
    allow_create: bool = False,
) -> int:
    """Safely increment and return the next sequence number under concurrency.

    Uses `SELECT ... FOR UPDATE` on PostgreSQL or atomic `UPDATE ... RETURNING` on SQLite.
    When allow_create is False (default for batches), raises ValueError if series is not found.
    """
    bind = db.get_bind()
    dialect = getattr(bind.dialect, "name", "")
    club, ay, code = resolve_club_and_academic_year(db, club_id, academic_year, club_code)

    if dialect == "postgresql":
        stmt = (
            select(NumberingSeries)
            .where(
                NumberingSeries.club_id == club_id,
                NumberingSeries.key == series_key,
                NumberingSeries.academic_year == ay,
            )
            .with_for_update()
        )
        ns = db.scalars(stmt).first()
        if not ns:
            if allow_create:
                fmt = format_pattern or f"{code}/{{academic_year}}/{series_key}/{{seq:03d}}"
                ns = NumberingSeries(
                    club_id=club_id,
                    key=series_key,
                    format=fmt,
                    academic_year=ay,
                    last_seq=1,
                )
                db.add(ns)
                db.flush()
                return 1
            raise ValueError(
                f"Numbering series '{series_key}' for academic year '{ay}' not found in club '{club.name}'. "
                "Please ask an administrator to create the numbering series."
            )
        ns.last_seq += 1
        db.flush()
        return ns.last_seq

    # SQLite (3.35+) / Generic: atomic UPDATE ... RETURNING
    stmt_upd = (
        update(NumberingSeries)
        .where(
            NumberingSeries.club_id == club_id,
            NumberingSeries.key == series_key,
            NumberingSeries.academic_year == ay,
        )
        .values(last_seq=NumberingSeries.last_seq + 1)
        .returning(NumberingSeries.last_seq)
    )
    val = db.execute(stmt_upd).scalar_one_or_none()
    if val is not None:
        db.flush()
        return val

    # If row was not updated, check whether series exists
    series_repo = ScopedRepository(db, NumberingSeries, club_id=club_id)
    ns = series_repo.find_first(
        NumberingSeries.key == series_key,
        NumberingSeries.academic_year == ay,
    )
    if not ns:
        if allow_create:
            fmt = format_pattern or f"{code}/{{academic_year}}/{series_key}/{{seq:03d}}"
            ns = NumberingSeries(
                club_id=club_id,
                key=series_key,
                format=fmt,
                academic_year=ay,
                last_seq=1,
            )
            db.add(ns)
            db.flush()
            return 1
        raise ValueError(
            f"Numbering series '{series_key}' for academic year '{ay}' not found in club '{club.name}'. "
            "Please ask an administrator to create the numbering series."
        )

    ns.last_seq += 1
    db.flush()
    return ns.last_seq


def get_suggested_ref_no_for_series(
    db: Session,
    club_id: str,
    series_key: str,
    academic_year: Optional[str] = None,
    event_code: Optional[str] = None,
    format_pattern: Optional[str] = None,
) -> str:
    """Peek the next suggested reference number without incrementing the counter."""
    club, ay, code = resolve_club_and_academic_year(db, club_id, academic_year)
    series_repo = ScopedRepository(db, NumberingSeries, club_id=club_id)
    ns = series_repo.find_first(
        NumberingSeries.key == series_key,
        NumberingSeries.academic_year == ay,
    )
    next_seq = (ns.last_seq + 1) if ns else 1
    fmt = (ns.format if ns and ns.format else None) or format_pattern or f"{code}/{{academic_year}}/{{series}}/{{seq:03d}}"
    return format_reference_number(
        format_pattern=fmt,
        academic_year=ay,
        series_key=series_key,
        seq=next_seq,
        club_code=code,
        event_code=event_code or series_key,
    )


def reserve_number_for_document(
    db: Session,
    club_id: str,
    user_id: str,
    series_key: str,
    academic_year: Optional[str] = None,
    event_code: Optional[str] = None,
    format_pattern: Optional[str] = None,
    expiry_minutes: int = 30,
    status: str = "reserved",
    document_id: Optional[str] = None,
    allow_create: bool = False,
) -> tuple[NumberReservation, str]:
    """Atomically allocate sequence number and create a NumberReservation record."""
    club, ay, code = resolve_club_and_academic_year(db, club_id, academic_year)

    seq = allocate_next_sequence(
        db=db,
        club_id=club_id,
        series_key=series_key,
        academic_year=ay,
        club_code=code,
        format_pattern=format_pattern,
        allow_create=allow_create,
    )

    series_repo = ScopedRepository(db, NumberingSeries, club_id=club_id)
    ns = series_repo.find_first(
        NumberingSeries.key == series_key,
        NumberingSeries.academic_year == ay,
    )
    fmt = (ns.format if ns and ns.format else None) or format_pattern or f"{code}/{{academic_year}}/{{series}}/{{seq:03d}}"
    event_code_val = event_code or series_key
    ref_no = format_reference_number(
        format_pattern=fmt,
        academic_year=ay,
        series_key=series_key,
        seq=seq,
        club_code=code,
        event_code=event_code_val,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    reservation = NumberReservation(
        id=str(uuid.uuid4()),
        club_id=club_id,
        user_id=user_id,
        series_key=series_key,
        academic_year=ay,
        sequence_num=seq,
        ref_no=ref_no,
        expires_at=now + timedelta(minutes=expiry_minutes),
        status=status,
        used_at=now if status == "used" else None,
        document_id=document_id,
    )
    db.add(reservation)
    db.flush()
    return reservation, ref_no
