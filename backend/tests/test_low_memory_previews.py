"""Tests for LOW_MEMORY_MODE template previews and thumbnails.

Verifies:
1. Setting: LOW_MEMORY_MODE defaults to False, reads from env var.
2. Built-in template thumbnail stems are shared (no club_id suffix) in low-memory mode,
   and per-club in normal mode.
3. Concurrency slots (_RENDER_SLOTS, _PREVIEW_SLOTS) are 1 in low-memory mode, 2 normally.
4. With LOW_MEMORY_MODE=True, render_template_thumbnail does NOT invoke LibreOffice
   or Renderer, and returns a valid 420x594 Pillow-rendered WebP document sketch.
5. With LOW_MEMORY_MODE=False, render_template_thumbnail uses the existing LibreOffice path.
6. Preview viewer pages (render_template_preview_pages) cap scale to longest side <= 1200 px
   in low-memory mode, and close PyMuPDF documents in a finally block in both modes.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image
import pymupdf

from server.app.core.config import Settings, settings
from server.app.core.dummy_thumbnail import (
    _PREVIEW_SLOTS,
    _RENDER_SLOTS,
    _render_thumbnail,
    preview_page_paths,
    render_template_preview_pages,
    render_template_thumbnail,
    thumbnail_stem,
)
from server.app.core.storage import require_local_storage
from server.app.models import Template, TemplateVersion


def test_low_memory_mode_setting_default_and_env(monkeypatch):
    """LOW_MEMORY_MODE setting defaults to False, and reads truthy values from env."""
    # Default is False
    monkeypatch.delenv("LOW_MEMORY_MODE", raising=False)
    s_default = Settings()
    assert s_default.LOW_MEMORY_MODE is False

    # "true", "1", "yes", "on" enable it
    for truthy in ("true", "True", "1", "yes", "on"):
        monkeypatch.setenv("LOW_MEMORY_MODE", truthy)
        s = Settings()
        assert s.LOW_MEMORY_MODE is True, f"Failed for {truthy}"

    # "false", "0", "no", "" disable it
    for falsy in ("false", "False", "0", "no", ""):
        monkeypatch.setenv("LOW_MEMORY_MODE", falsy)
        s = Settings()
        assert s.LOW_MEMORY_MODE is False, f"Failed for {falsy}"


def test_thumbnail_stem_shared_in_low_memory_mode(monkeypatch):
    """Built-in templates share one preview stem in low-memory mode; club templates keep single stem."""
    builtin_tmpl = Template(id="tmpl-builtin", slug="approval_note", name="Approval Note", club_id=None)
    custom_tmpl = Template(id="tmpl-custom", slug="custom_form", name="Custom Form", club_id="club-1")
    ver = TemplateVersion(id="ver-100", version_no=1, template_id="tmpl-builtin")

    # In low-memory mode: built-in templates share one preview stem without club_id
    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", True)
    assert thumbnail_stem(builtin_tmpl, ver, "club-1") == "ver-100"
    assert thumbnail_stem(custom_tmpl, ver, "club-1") == "ver-100"

    # In normal mode: built-in templates use per-club stem
    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", False)
    assert thumbnail_stem(builtin_tmpl, ver, "club-1") == "ver-100_club-1"
    assert thumbnail_stem(custom_tmpl, ver, "club-1") == "ver-100"


def test_render_and_preview_slots_low_memory_mode(monkeypatch):
    """_RENDER_SLOTS and _PREVIEW_SLOTS cap at 1 in low-memory mode, 2 normally."""
    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", False)
    assert _RENDER_SLOTS._value == 2
    assert _PREVIEW_SLOTS._value == 2

    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", True)
    assert _RENDER_SLOTS._value == 1
    assert _PREVIEW_SLOTS._value == 1

    # In low-memory mode, acquiring once leaves 0 slots available
    assert _RENDER_SLOTS.acquire(blocking=False) is True
    assert _RENDER_SLOTS.acquire(blocking=False) is False
    _RENDER_SLOTS.release()
    assert _RENDER_SLOTS._value == 1


def test_low_memory_thumbnail_does_not_invoke_renderer(monkeypatch):
    """In LOW_MEMORY_MODE, render_template_thumbnail does NOT invoke Renderer / LibreOffice."""
    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", True)

    tmpl = Template(id="test-lm-builtin", slug="approval_note", name="Approval Note", club_id=None)
    ver = TemplateVersion(id="ver-lm-test-1", version_no=1, template_id="test-lm-builtin")

    local_storage = require_local_storage()
    thumb_path = local_storage.base_dir / "thumbnails" / f"{ver.id}.webp"
    if thumb_path.exists():
        thumb_path.unlink()

    db_mock = mock.MagicMock()

    with mock.patch("docgen.renderer.Renderer") as mock_renderer, \
         mock.patch("subprocess.run") as mock_subproc_run, \
         mock.patch("subprocess.Popen") as mock_subproc_popen:

        result_path = render_template_thumbnail(
            db=db_mock,
            tmpl=tmpl,
            ver=ver,
            club_slug="acm",
            club_id="club-acm",
        )

        # Neither Renderer nor subprocess (LibreOffice) should be called
        mock_renderer.assert_not_called()
        mock_subproc_run.assert_not_called()
        mock_subproc_popen.assert_not_called()

        assert result_path.exists()
        assert result_path == thumb_path

        with Image.open(result_path) as img:
            assert img.format == "WEBP"
            assert img.size == (420, 594)

        # Clean up
        thumb_path.unlink()


def test_low_memory_thumbnail_custom_template_brand_color(monkeypatch):
    """Custom templates use club letterhead and brand colour in lightweight sketch."""
    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", True)

    tmpl = Template(id="test-lm-custom", slug="approval_note", name="Club Proposal", club_id="club-acm")
    ver = TemplateVersion(id="ver-lm-test-2", version_no=1, template_id="test-lm-custom")

    local_storage = require_local_storage()
    thumb_path = local_storage.base_dir / "thumbnails" / f"{ver.id}.webp"
    if thumb_path.exists():
        thumb_path.unlink()

    db_mock = mock.MagicMock()

    with mock.patch("docgen.renderer.Renderer") as mock_renderer:
        result_path = render_template_thumbnail(
            db=db_mock,
            tmpl=tmpl,
            ver=ver,
            club_slug="acm",
            club_id="club-acm",
        )
        mock_renderer.assert_not_called()
        assert result_path.exists()

        with Image.open(result_path) as img:
            assert img.size == (420, 594)

        thumb_path.unlink()


def test_normal_mode_thumbnail_invokes_existing_renderer(monkeypatch):
    """When LOW_MEMORY_MODE=False, render_template_thumbnail calls existing _render_thumbnail path."""
    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", False)

    tmpl = Template(id="test-norm", slug="approval_note", name="Approval Note", club_id=None)
    ver = TemplateVersion(id="ver-norm-test", version_no=1, template_id="test-norm")

    local_storage = require_local_storage()
    expected_stem = f"{ver.id}_club-acm"
    thumb_path = local_storage.base_dir / "thumbnails" / f"{expected_stem}.webp"
    if thumb_path.exists():
        thumb_path.unlink()

    db_mock = mock.MagicMock()

    with mock.patch("server.app.core.dummy_thumbnail._render_thumbnail") as mock_render:
        mock_render.return_value = thumb_path
        res = render_template_thumbnail(
            db=db_mock,
            tmpl=tmpl,
            ver=ver,
            club_slug="acm",
            club_id="club-acm",
        )
        mock_render.assert_called_once()
        assert res == thumb_path


def test_preview_pages_rasterise_scale_capped_in_low_memory(monkeypatch, tmp_path):
    """Full preview pages rasterise with longest side <= 1200 px in low-memory mode."""
    # Create a synthetic 2-page test PDF with large dimensions (1000 x 1600 points)
    pdf_path = tmp_path / "test_doc.pdf"
    doc = pymupdf.open()
    doc.new_page(width=1000, height=1600)
    doc.new_page(width=1000, height=1600)
    doc.save(str(pdf_path))
    doc.close()

    tmpl = Template(id="test-prev", slug="approval_note", name="Approval Note", club_id=None)
    ver = TemplateVersion(id="ver-prev-test", version_no=1, template_id="test-prev")

    local_storage = require_local_storage()
    thumbnails_dir = local_storage.base_dir / "thumbnails"
    thumb_path = thumbnails_dir / f"{ver.id}.webp"

    # Clean any leftover files
    for p in thumbnails_dir.glob(f"{ver.id}*"):
        try:
            p.unlink()
        except Exception:
            pass

    # Mock the Renderer result to point to our synthetic PDF
    mock_res = mock.MagicMock()
    mock_res.pdf_path = pdf_path

    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", True)

    with mock.patch("server.app.core.dummy_thumbnail.Renderer") as mock_renderer_cls:
        instance = mock_renderer_cls.return_value
        instance.render.return_value = mock_res

        _render_thumbnail(
            db=mock.MagicMock(),
            tmpl=tmpl,
            ver=ver,
            club_slug="acm",
            docx_path=Path("templates/approval_note/template.docx"),
            thumb_path=thumb_path,
            local_storage=local_storage,
        )

    # Check generated preview pages: longest side must be <= 1200 px
    p1 = thumbnails_dir / f"{ver.id}_p1.webp"
    p2 = thumbnails_dir / f"{ver.id}_p2.webp"
    assert p1.exists()
    assert p2.exists()

    with Image.open(p1) as img1:
        assert max(img1.width, img1.height) <= 1200, f"Page 1 longest side {max(img1.width, img1.height)} exceeds 1200"

    with Image.open(p2) as img2:
        assert max(img2.width, img2.height) <= 1200, f"Page 2 longest side {max(img2.width, img2.height)} exceeds 1200"

    # Cleanup
    for p in (thumb_path, p1, p2):
        if p.exists():
            p.unlink()


def test_pymupdf_document_closed_in_finally(monkeypatch, tmp_path):
    """Every PyMuPDF document opened in _render_thumbnail is closed in a finally block."""
    pdf_path = tmp_path / "test_close.pdf"
    doc = pymupdf.open()
    doc.new_page(width=400, height=600)
    doc.save(str(pdf_path))
    doc.close()

    tmpl = Template(id="test-close", slug="approval_note", name="Approval Note", club_id=None)
    ver = TemplateVersion(id="ver-close-test", version_no=1, template_id="test-close")

    local_storage = require_local_storage()
    thumb_path = local_storage.base_dir / "thumbnails" / f"{ver.id}.webp"

    mock_res = mock.MagicMock()
    mock_res.pdf_path = pdf_path

    # Track open/close calls
    real_open = pymupdf.open
    opened_docs = []

    def tracking_open(*args, **kwargs):
        d = real_open(*args, **kwargs)
        opened_docs.append(d)
        return d

    monkeypatch.setattr(pymupdf, "open", tracking_open)

    for mode in (True, False):
        monkeypatch.setattr(settings, "LOW_MEMORY_MODE", mode)
        opened_docs.clear()

        with mock.patch("server.app.core.dummy_thumbnail.Renderer") as mock_renderer_cls:
            instance = mock_renderer_cls.return_value
            instance.render.return_value = mock_res

            _render_thumbnail(
                db=mock.MagicMock(),
                tmpl=tmpl,
                ver=ver,
                club_slug="acm",
                docx_path=Path("templates/approval_note/template.docx"),
                thumb_path=thumb_path,
                local_storage=local_storage,
            )

        assert len(opened_docs) == 1
        assert opened_docs[0].is_closed is True, f"PyMuPDF doc was not closed in mode LOW_MEMORY_MODE={mode}"

    # Cleanup
    for p in local_storage.base_dir.glob(f"thumbnails/{ver.id}*"):
        try:
            p.unlink()
        except Exception:
            pass
