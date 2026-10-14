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


class ClubConfig(BaseModel):
    club_name: str = "ACM Student Chapter, SVNIT"
    club_short: str = "ACM"
    institute_name: str = "Sardar Vallabhbhai National Institute of Technology, Surat (SVNIT)"
    institute_short: str = "SVNIT"
    chapter_code: str = "6/52"
    head_of_account: str = "6/52"
    academic_year: str = "2026-27"

    letterheads: dict[str, LetterheadConfig] = Field(default_factory=dict)

    # Office bearers
    student_head: Optional[PersonConfig] = None
    student_secretary: Optional[PersonConfig] = None
    chairperson: Optional[PersonConfig] = None
    faculty_chairman: Optional[PersonConfig] = None
    faculty_co_chairman: Optional[PersonConfig] = None

    # Approval chain
    approval_chain: list[str] = Field(default_factory=lambda: [
        "Chairman F&SW",
        "Associate Dean SW",
        "Dean SW",
    ])

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
