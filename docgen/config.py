"""Configuration loader for club_config.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


class LetterheadConfig(BaseModel):
    name: str
    logo_path: Optional[str] = None
    crest_path: Optional[str] = None
    header_text: Optional[str] = None
    font: str = "Times New Roman"
    color: str = "#000000"


class PersonConfig(BaseModel):
    name: str
    admission_no: Optional[str] = None
    branch: Optional[str] = None
    mobile: Optional[str] = None  # placeholder in example
    email: Optional[str] = None
    roles: dict[str, str] = Field(default_factory=dict)


class VenueConfig(BaseModel):
    full_name: str
    short_name: Optional[str] = None
    default_addressee: Optional[str] = None
    tech_assistant: Optional[PersonConfig] = None
    faculty_in_charge: Optional[PersonConfig] = None


class NumberingConfig(BaseModel):
    last_used: int = 0


DEFAULT_APPROVAL_CHAIN = (
    "\nChairman, F& SW",
    "\nAssociate Dean(SW)",
    "\nDean (Students Welfare)",
)


class ClubConfig(BaseModel):
    # Club identity comes from the club's own record; no club's values are defaults.
    club_name: str = ""
    club_short: str = ""
    institute_name: str = "Sardar Vallabhbhai National Institute of Technology, Surat (SVNIT)"
    institute_short: str = "SVNIT"
    chapter_code: str = ""
    head_of_account: str = ""
    academic_year: str = "2026-27"
    # Owning department, e.g. "Computer Science & Engineering" / "CSE" (for HoD lines, branches).
    department: str = ""
    department_short: str = ""
    # Full-width header banner for letter-style system templates. When unset, one is
    # composed from the institute crest, the club name and the club logo.
    letterhead_banner_path: Optional[str] = None
    club_logo_path: Optional[str] = None
    # Brand kit: accent colour for composed banners, footer line on generated documents.
    brand_color: str = "#4F81BD"
    footer_text: str = ""

    letterheads: dict[str, LetterheadConfig] = Field(default_factory=dict)

    # Office bearers
    student_head: Optional[PersonConfig] = None
    student_secretary: Optional[PersonConfig] = None
    chairperson: Optional[PersonConfig] = None
    faculty_chairman: Optional[PersonConfig] = None
    faculty_co_chairman: Optional[PersonConfig] = None

    # Approval chain: "Name\nDesignation" entries in signing order. Names are per-institute
    # data and belong in club settings; the default carries designations only.
    approval_chain: list[str] = Field(default_factory=lambda: list(DEFAULT_APPROVAL_CHAIN))

    def approval_signatories(self, count: int = 3) -> list[dict[str, str]]:
        """approval_chain as [{name, designation}], padded to ``count`` entries."""
        out: list[dict[str, str]] = []
        for entry in self.approval_chain[:count]:
            name, _, designation = str(entry or "").partition("\n")
            out.append({"name": name.strip(), "designation": designation.strip()})
        while len(out) < count:
            _, _, designation = DEFAULT_APPROVAL_CHAIN[len(out) % len(DEFAULT_APPROVAL_CHAIN)].partition("\n")
            out.append({"name": "", "designation": designation.strip()})
        return out

    # Venue registry
    venues: dict[str, VenueConfig] = Field(default_factory=dict)

    # Standing defaults
    defaults: dict[str, Any] = Field(default_factory=lambda: {
        "purchase_order": "NiL",
        "advance": "NiL",
        "laboratory_office": "Student Council",
        "mode": "Offline",
    })

    # Numbering series
    numbering: dict[str, NumberingConfig] = Field(default_factory=dict)

    affiliating_institute_text: str = (
        "Sardar Vallabhbhai National Institute of Technology, Surat (SVNIT)"
    )

    def next_number(self, series: str) -> int:
        """Get and increment the next number for a series."""
        if series not in self.numbering:
            self.numbering[series] = NumberingConfig()
        self.numbering[series].last_used += 1
        return self.numbering[series].last_used

    def get_venue(self, venue_name: str) -> Optional[VenueConfig]:
        """Fuzzy-match venue by name."""
        name_lower = venue_name.lower()
        for key, venue in self.venues.items():
            if (key.lower() in name_lower or
                name_lower in key.lower() or
                (venue.short_name and venue.short_name.lower() in name_lower)):
                return venue
        return None


def load_config(config_path: str | Path | None = None) -> ClubConfig:
    """Load club config from YAML file."""
    if config_path is None:
        # Try standard locations
        candidates = [
            Path("config/club_config.yaml"),
            Path("config/club_config.example.yaml"),
        ]
        for p in candidates:
            if p.exists():
                config_path = p
                break
        if config_path is None:
            # Return defaults
            return ClubConfig()

    config_path = Path(config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return ClubConfig(**data)
