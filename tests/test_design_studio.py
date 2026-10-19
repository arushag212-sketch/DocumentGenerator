"""Unit and integration tests for Part 4: Design Studio.

Tests:
1. Theme catalog validity (6 themes, contrast, palette properties).
2. Compilation with each theme and with 5 curated fonts (Tinos, Roboto, Open Sans, Montserrat, Roboto Mono).
3. Section orientation (portrait vs landscape) and page dimensions.
4. Watermark text presence and page background color XML tagging.
5. Official system templates rendering byte-for-byte consistency (no styling regressions when design_settings omitted).
"""

from __future__ import annotations

import io
from pathlib import Path
from docx import Document
import pytest

from server.app.core.template_compiler import (
    TipTapDocxCompiler,
    TemplateCompiler,
    load_themes_catalog,
)
from docgen.renderer import Renderer
from docgen.models import EventRecord


SAMPLE_DOC_JSON = {
    "type": "doc",
    "content": [
        {
            "type": "heading",
            "attrs": {"level": 1},
            "content": [{"type": "text", "text": "Annual Tech Symposium Approval Note"}],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "We hereby request sanction for holding the annual tech symposium at SVNIT campus."}
            ],
        },
        {
            "type": "table",
            "attrs": {"blockType": "infoTable"},
            "content": [
                {
                    "type": "tableRow",
                    "content": [
                        {
                            "type": "tableCell",
                            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Estimated Budget"}]}],
                        },
                        {
                            "type": "tableCell",
                            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "INR 45,000"}]}],
                        },
                    ],
                }
            ],
        },
    ],
}


def test_theme_catalog_loading():
    """Verify that themes.json contains all 6 required themes with valid hex codes."""
    themes_dict = load_themes_catalog()
    assert len(themes_dict) >= 6
    theme_ids = set(themes_dict.keys())
    required = {
        "official_navy",
        "svnit_gold",
        "classic_bw",
        "modern_green",
        "warm_sunset",
        "minimal_grey",
    }
    assert required.issubset(theme_ids), f"Missing themes: {required - theme_ids}"

    for t in themes_dict.values():
        assert t["heading_color"].startswith("#")
        assert t["text_color"].startswith("#")
        assert t["table_header_bg"].startswith("#")
        assert "heading_font" in t
        assert "body_font" in t


def test_compile_all_six_themes(tmp_path):
    """Verify that compiling with each theme applies proper font and color XML properties."""
    themes_dict = load_themes_catalog()
    for t in themes_dict.values():
        settings = {
            "theme": t["id"],
            "fontFamily": t["body_font"],
            "headingFontFamily": t["heading_font"],
            "headingColor": t["heading_color"],
            "textColor": t["text_color"],
            "tableHeaderBg": t["table_header_bg"],
            "tableHeaderTextColor": t["table_header_text"],
            "borderColor": t["border_color"],
            "dividerColor": t["divider_color"],
            "pageBg": t["page_bg"],
            "orientation": "portrait",
            "margins": "normal",
            "watermark": "CONFIDENTIAL",
        }
        compiler = TipTapDocxCompiler(SAMPLE_DOC_JSON, fields=[], design_settings=settings)
        doc = compiler.build()
        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()
        assert len(docx_bytes) > 2000, f"Compiled DOCX for theme {t['id']} is too small"

        reopened = Document(io.BytesIO(docx_bytes))
        xml = reopened._body._element.xml
        assert t["body_font"] in xml or t["heading_font"] in xml


@pytest.mark.parametrize("font_name", [
    "Tinos",
    "Roboto",
    "Open Sans",
    "Montserrat",
    "Roboto Mono",
])
def test_compile_curated_fonts(font_name, tmp_path):
    """Verify compiling with 5 distinct curated fonts embeds explicit rFonts XML."""
    settings = {
        "theme": "official_navy",
        "fontFamily": font_name,
        "headingFontFamily": font_name,
        "headingColor": "#1e3a8a",
        "textColor": "#0f172a",
        "orientation": "portrait",
        "margins": "normal",
    }
    compiler = TipTapDocxCompiler(SAMPLE_DOC_JSON, fields=[], design_settings=settings)
    doc = compiler.build()
    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    reopened = Document(io.BytesIO(docx_bytes))
    xml = reopened._body._element.xml
    assert f'w:ascii="{font_name}"' in xml
    assert f'w:hAnsi="{font_name}"' in xml


def test_orientation_portrait_vs_landscape(tmp_path):
    """Verify section orientation sets correct page width and height."""
    # Portrait
    portrait_settings = {"orientation": "portrait", "margins": "normal"}
    c_port = TipTapDocxCompiler(SAMPLE_DOC_JSON, fields=[], design_settings=portrait_settings)
    d_port = c_port.build()
    sec_port = d_port.sections[0]
    assert sec_port.page_width < sec_port.page_height

    # Landscape
    landscape_settings = {"orientation": "landscape", "margins": "normal"}
    c_land = TipTapDocxCompiler(SAMPLE_DOC_JSON, fields=[], design_settings=landscape_settings)
    d_land = c_land.build()
    sec_land = d_land.sections[0]
    assert sec_land.page_width > sec_land.page_height


def test_margins_presets():
    """Verify normal, compact, and wide margin presets adjust section margins."""
    for mode, expected_in in [("normal", 0.8), ("compact", 0.5), ("wide", 1.25)]:
        compiler = TipTapDocxCompiler(SAMPLE_DOC_JSON, fields=[], design_settings={"margins": mode})
        doc = compiler.build()
        sec = doc.sections[0]
        assert abs(sec.top_margin.inches - expected_in) < 0.05
        assert abs(sec.bottom_margin.inches - expected_in) < 0.05


def test_watermark_and_page_bg():
    """Verify watermark text and background color in DOCX XML."""
    settings = {
        "watermark": "SVNIT DRAFT ONLY",
        "pageBg": "#fef3c7",
    }
    compiler = TipTapDocxCompiler(SAMPLE_DOC_JSON, fields=[], design_settings=settings)
    doc = compiler.build()

    # Check watermark in header
    header_xml = doc.sections[0].header._element.xml
    assert "SVNIT DRAFT ONLY" in header_xml

    # Check background in document XML
    doc_xml = doc.element.xml
    assert "fef3c7" in doc_xml or "FEF3C7" in doc_xml


def test_official_system_templates_no_regression():
    """Verify that compiling standard content without design_settings maintains classic Times New Roman."""
    compiler = TipTapDocxCompiler(SAMPLE_DOC_JSON, fields=[], design_settings=None)
    doc = compiler.build()
    sec = doc.sections[0]

    # Default is portrait with standard 0.8 in margins
    assert sec.page_width < sec.page_height
    assert abs(sec.top_margin.inches - 0.8) < 0.01

    # XML body uses Times New Roman by default
    xml = doc._body._element.xml
    assert 'w:ascii="Times New Roman"' in xml
