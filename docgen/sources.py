"""Context and template source abstraction for docgen.

Enables docgen to accept injected ClubContext and TemplateSource from database
rows or API requests while preserving full backwards compatibility with file-based
ClubConfig and templates_dir.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional, Protocol, Union

import yaml
from docgen.config import ClubConfig, LetterheadConfig, PersonConfig, VenueConfig, NumberingConfig
from docgen.schema import TemplateSchema, load_schema


class TemplateSource(Protocol):
    """Protocol for providing template DOCX and schema."""

    def get_template_docx_stream(self, template_id: str) -> io.BytesIO | Path:
        """Return either a file Path or BytesIO of the template.docx."""
        ...

    def get_template_schema(self, template_id: str) -> TemplateSchema:
        """Return the parsed TemplateSchema."""
        ...


class FileSystemTemplateSource:
    """Default template source that loads from the filesystem templates_dir."""

    def __init__(self, templates_dir: str | Path = "templates"):
        self.templates_dir = Path(templates_dir)

    def get_template_docx_stream(self, template_id: str) -> Path:
        p = self.templates_dir / template_id / "template.docx"
        if not p.exists():
            raise FileNotFoundError(f"No template.docx in {self.templates_dir / template_id}")
        return p

    def get_template_schema(self, template_id: str) -> TemplateSchema:
        return load_schema(self.templates_dir / template_id)


class DatabaseTemplateSource:
    """Template source that loads from database models (TemplateVersion & storage)."""

    def __init__(self, session_or_templates: Any):
        """
        Can be initialized with a dictionary of {template_slug: (schema_yaml_str, docx_bytes_or_path)}
        or an active SQLAlchemy Session.
        """
        self.data_store: dict[str, tuple[str, Union[bytes, Path]]] = {}
        if isinstance(session_or_templates, dict):
            self.data_store = session_or_templates
        else:
            self._load_from_db(session_or_templates)

    def _load_from_db(self, db_session: Any) -> None:
        from server.app.models import Template, TemplateVersion
        versions = (
            db_session.query(Template, TemplateVersion)
            .join(TemplateVersion, Template.current_version_id == TemplateVersion.id)
            .all()
        )
        for tmpl, ver in versions:
            docx_path = Path(ver.docx_storage_key)
            self.data_store[tmpl.slug] = (ver.schema_yaml, docx_path)
            self.data_store[tmpl.id] = (ver.schema_yaml, docx_path)

    def get_template_docx_stream(self, template_id: str) -> io.BytesIO | Path:
        if template_id not in self.data_store:
            raise FileNotFoundError(f"Template '{template_id}' not found in database source")
        _, docx_ref = self.data_store[template_id]
        if isinstance(docx_ref, bytes):
            return io.BytesIO(docx_ref)
        if isinstance(docx_ref, Path) and docx_ref.exists():
            return docx_ref
        if isinstance(docx_ref, str) and Path(docx_ref).exists():
            return Path(docx_ref)
        raise FileNotFoundError(f"Template DOCX file not found for '{template_id}': {docx_ref}")

    def get_template_schema(self, template_id: str) -> TemplateSchema:
        if template_id not in self.data_store:
            raise FileNotFoundError(f"Template '{template_id}' not found in database source")
        schema_yaml_str, _ = self.data_store[template_id]
        data = yaml.safe_load(schema_yaml_str)
        return TemplateSchema(**data)


def build_club_config_from_db(db_session: Any, club_slug: str) -> ClubConfig:
    """Build a standard ClubConfig domain object entirely from database rows."""
    from server.app.models import Club, Person, RoleHeld, Venue, NumberingSeries, Asset, Letterhead

    club = db_session.query(Club).filter(Club.slug == club_slug).first()
    if not club:
        raise ValueError(f"Club with slug '{club_slug}' not found in database.")

    # Letterheads
    letterheads_map: dict[str, LetterheadConfig] = {}
    letterheads = db_session.query(Letterhead).filter(
        (Letterhead.club_id == club.id) | (Letterhead.club_id.is_(None))
    ).all()
    for lh in letterheads:
        lh_key = lh.name.lower().replace(" ", "_")
        letterheads_map[lh_key] = LetterheadConfig(
            name=lh.name,
            header_text=lh.title_text,
            font=lh.fonts.get("primary", "Times New Roman") if isinstance(lh.fonts, dict) else "Times New Roman",
            color=lh.colors.get("primary", "#000000") if isinstance(lh.colors, dict) else "#000000",
        )

    # People and Roles
    roles = db_session.query(RoleHeld, Person).join(Person, RoleHeld.person_id == Person.id).filter(
        RoleHeld.club_id == club.id
    ).all()

    student_head = None
    student_secretary = None
    chairperson = None
    faculty_chairman = None
    faculty_co_chairman = None

    for role, person in roles:
        p_cfg = PersonConfig(
            name=person.full_name,
            admission_no=person.roll_no or "",
            branch=person.branch or person.department or "",
            mobile=person.mobile or "",
            email=person.email or "",
            roles={role.role_key: role.designation_label},
        )
        if role.role_key == "student_head":
            student_head = p_cfg
        elif role.role_key == "student_secretary":
            student_secretary = p_cfg
        elif role.role_key == "chairperson":
            chairperson = p_cfg
        elif role.role_key == "faculty_chairman":
            faculty_chairman = p_cfg
        elif role.role_key == "faculty_co_chairman":
            faculty_co_chairman = p_cfg

    # Venues
    venues_map: dict[str, VenueConfig] = {}
    venues = db_session.query(Venue).filter(
        (Venue.club_id == club.id) | (Venue.club_id.is_(None))
    ).all()
    for v in venues:
        tech_ast = None
        if v.tech_assistant_person_id:
            tp = db_session.query(Person).filter(Person.id == v.tech_assistant_person_id).first()
            if tp:
                tech_ast = PersonConfig(
                    name=tp.full_name,
                    admission_no=tp.roll_no or "",
                    branch=tp.branch or tp.department or "",
                    mobile=tp.mobile or "",
                    email=tp.email or "",
                    roles={"permission_letter": "Tech Assistant , Seminar Hall"},
                )
        fac_inc = None
        if v.faculty_incharge_person_id:
            fp = db_session.query(Person).filter(Person.id == v.faculty_incharge_person_id).first()
            if fp:
                fac_inc = PersonConfig(
                    name=fp.full_name,
                    admission_no=fp.roll_no or "",
                    branch=fp.branch or fp.department or "",
                    mobile=fp.mobile or "",
                    email=fp.email or "",
                    roles={"permission_letter": "Faculty In-charge , Seminar Hall"},
                )
        venues_map[v.name] = VenueConfig(
            full_name=v.name,
            short_name=v.short_name,
            default_addressee=v.addressee_default,
            tech_assistant=tech_ast,
            faculty_in_charge=fac_inc,
        )

    # Numbering
    numbering_map: dict[str, NumberingConfig] = {}
    nums = db_session.query(NumberingSeries).filter(NumberingSeries.club_id == club.id).all()
    for n in nums:
        numbering_map[n.key] = NumberingConfig(last_used=n.last_seq)

    # Defaults and settings from club
    std_defaults = {
        "purchase_order": "NiL",
        "advance": "NiL",
        "laboratory_office": "Student Council",
        "mode": "Offline",
    }
    club_defaults = club.settings.get("defaults", {})
    defaults = {**std_defaults, **club_defaults}

    approval_chain = club.settings.get("approval_chain", [
        "Dr. Rakesh Maurya\nChairman F&SW",
        "Dr. Manish K Rathod\nAssociate Dean SW",
        "Dr. Sanjay R. Patel\nDean SW",
    ])

    return ClubConfig(
        club_name=club.name,
        club_short=club.short_name,
        institute_name=club.settings.get("institute_name", "Sardar Vallabhbhai National Institute of Technology, Surat (SVNIT)"),
        institute_short=club.settings.get("institute_short", "SVNIT"),
        chapter_code=club.chapter_code or "6/52",
        head_of_account=club.head_of_account or "6/52",
        academic_year=club.academic_year_default or "2026-27",
        letterheads=letterheads_map,
        student_head=student_head,
        student_secretary=student_secretary,
        chairperson=chairperson,
        faculty_chairman=faculty_chairman,
        faculty_co_chairman=faculty_co_chairman,
        approval_chain=approval_chain,
        venues=venues_map,
        defaults=defaults,
        numbering=numbering_map,
        affiliating_institute_text=club.settings.get(
            "affiliating_institute_text",
            "Sardar Vallabhbhai National Institute of Technology, Surat (SVNIT)"
        ),
    )
