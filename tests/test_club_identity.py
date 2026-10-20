"""System templates and defaults use each club's own data, never another club's."""

from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace

from docgen.config import ClubConfig
from docgen.letterhead_banner import PLACEHOLDER_NAME
from docgen.renderer import Renderer
from docgen.sources import DatabaseTemplateSource
from server.app.core.club_identity import default_addressee, default_signatures
from tests.fixtures.sih_event import get_sih_fixture

SYSTEM_TEMPLATES = ["permission_letter", "approval_note", "prize_money_receipt", "bill_summary", "bill_certificate", "mom"]


def _template_text(slug: str) -> str:
    z = zipfile.ZipFile(Path("templates") / slug / "template.docx")
    return " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))


def test_system_templates_have_no_club_specific_text():
    for slug in SYSTEM_TEMPLATES:
        text = _template_text(slug)
        for word in ("ACM", "Computer Science", "DoCSE", "Rakesh", "Rathod", "Maurya", "Alok Kumar"):
            assert word not in text, f"{slug} still hardcodes {word!r}"


def test_default_config_carries_no_club_values():
    cfg = ClubConfig()
    assert cfg.club_name == "" and cfg.club_short == ""
    assert cfg.chapter_code == "" and cfg.head_of_account == ""
    assert all(s["name"] == "" for s in cfg.approval_signatories())


def test_approval_chain_parsing_and_padding():
    cfg = ClubConfig(approval_chain=["Dr. A\nChairman, F& SW"])
    sigs = cfg.approval_signatories()
    assert sigs[0] == {"name": "Dr. A", "designation": "Chairman, F& SW"}
    assert sigs[1]["name"] == "" and sigs[1]["designation"] == "Associate Dean(SW)"
    assert len(sigs) == 3


def test_club_defaults_come_from_the_club():
    club = SimpleNamespace(name="Demo Robotics Club", settings={"department": "Mechanical Engineering", "department_short": "MED"})
    assert default_addressee(club) == "Head of Department, Mechanical Engineering"
    sigs = default_signatures(club)
    assert sigs[0]["designation"] == "Demo Robotics Club"
    assert sigs[1]["designation"] == "MED, SVNIT"

    bare = SimpleNamespace(name="New Club", settings={})
    assert default_addressee(bare) == "Head of Department"
    assert default_signatures(bare)[1]["designation"] == "SVNIT"


def test_renderer_swaps_header_banner_for_club(tmp_path):
    slug = "permission_letter"
    schema = (Path("templates") / slug / "schema.yaml").read_text(encoding="utf-8")
    source = DatabaseTemplateSource({slug: (schema, Path("templates") / slug / "template.docx")})
    cfg = ClubConfig(club_name="Demo Robotics Club", club_short="ROBO", department="Mechanical Engineering")
    result = Renderer(config=cfg, template_source=source, outputs_dir=tmp_path).render(
        slug, get_sih_fixture(), output_dir=tmp_path, convert_pdf=False, allow_blanks=True
    )

    placeholder = (Path("assets") / PLACEHOLDER_NAME).read_bytes()
    with zipfile.ZipFile(result.docx_path) as z:
        header_xml = " ".join(z.read(n).decode() for n in z.namelist() if n.startswith("word/header"))
        media = [z.read(n) for n in z.namelist() if n.startswith("word/media/")]
        body = z.read("word/document.xml").decode()
    assert PLACEHOLDER_NAME in header_xml
    assert placeholder not in media, "placeholder banner must be replaced with the club's banner"
    assert "Chairperson , ROBO" in body
    assert "ACM" not in body.replace("ACM/", "")  # fixture reference numbers aside
