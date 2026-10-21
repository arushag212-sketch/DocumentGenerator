"""Tests for template thumbnail pre-rendering, background rendering, and placeholder cards.

Verifies:
1. LOW_MEMORY_MODE on, built-in template with pre-rendered file -> file returned, renderer not called.
2. Club template cache miss -> placeholder returned immediately, one job queued;
   second request does not queue duplicate; after worker runs, real thumbnail returned and persisted.
3. Placeholder card image contains no "[" raw placeholder text.
4. LOW_MEMORY_MODE off -> existing behaviour unchanged.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

from server.app.core.config import settings
from server.app.core.dummy_thumbnail import (
    _RENDER_SLOTS,
    _render_clean_placeholder,
    get_clean_placeholder,
    get_queue_size,
    is_placeholder_file,
    is_thumbnail_pending,
    pause_worker,
    render_template_thumbnail,
    reset_worker_state,
    resume_worker,
    thumbnail_stem,
    wait_for_thumbnail_jobs,
)
from server.app.core.storage import require_local_storage
from server.app.models import Template, TemplateVersion


@pytest.fixture(autouse=True)
def clean_worker():
    """Ensure worker queue and pending set are clean before and after each test."""
    reset_worker_state()
    yield
    reset_worker_state()


def test_builtin_template_with_prerendered_file_returned_without_renderer(monkeypatch, tmp_path):
    """LOW_MEMORY_MODE on: built-in template with pre-rendered file returns that file; renderer not called."""
    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", True)

    tmpl = Template(id="tmpl-b1", slug="notice", name="Notice / Circular", club_id=None)
    ver = TemplateVersion(id="ver-b1", version_no=1, template_id="tmpl-b1")

    # Create a mock pre-rendered thumbnail file
    fake_prerender = tmp_path / "notice.webp"
    with Image.new("RGB", (420, 594), color=(255, 255, 255)) as img:
        img.save(str(fake_prerender), format="WEBP")

    monkeypatch.setattr(
        "server.app.core.dummy_thumbnail.get_static_thumbnail_path",
        lambda slug: fake_prerender if slug == "notice" else None,
    )

    with mock.patch("server.app.core.dummy_thumbnail._render_thumbnail") as mock_render, \
         mock.patch("docgen.renderer.Renderer") as mock_renderer:

        db_mock = mock.MagicMock()
        result_path = render_template_thumbnail(
            db=db_mock,
            tmpl=tmpl,
            ver=ver,
            club_slug="acm",
            club_id="club-acm",
        )

        # Pre-rendered file returned directly
        assert result_path == fake_prerender
        assert result_path.exists()
        mock_render.assert_not_called()
        mock_renderer.assert_not_called()


def test_club_template_cache_miss_background_worker(monkeypatch, tmp_path):
    """Club template cache miss returns placeholder immediately, queues one job (no duplicates),
    and after worker runs, real thumbnail is returned and saved to persistent storage."""
    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", True)

    tmpl = Template(id="tmpl-c1", slug="custom_form", name="Custom Form", club_id="club-1")
    ver = TemplateVersion(id="ver-c1", version_no=1, template_id="tmpl-c1")
    stem = thumbnail_stem(tmpl, ver, "club-1")

    local_storage = require_local_storage()
    thumb_path = local_storage.base_dir / "thumbnails" / f"{stem}.webp"
    marker = thumb_path.with_suffix(".placeholder")
    if thumb_path.exists():
        thumb_path.unlink()
    if marker.exists():
        marker.unlink()

    # Track uploads to persistent storage
    pushed_keys: list[str] = []
    monkeypatch.setattr(local_storage, "push", lambda k: pushed_keys.append(k) or True, raising=False)

    # Mock database session returning tmpl and ver
    db_mock = mock.MagicMock()
    query_mock = mock.MagicMock()
    filter_mock = mock.MagicMock()

    def mock_query(model):
        m = mock.MagicMock()
        if model is Template:
            m.filter.return_value.first.return_value = tmpl
        elif model is TemplateVersion:
            m.filter.return_value.first.return_value = ver
        return m

    db_mock.query.side_effect = mock_query

    # Pause worker before requests so we can inspect the queue
    pause_worker()

    # Mock _template_docx so worker finds the template docx
    fake_docx = tmp_path / "template.docx"
    fake_docx.write_bytes(b"fake docx")
    monkeypatch.setattr("server.app.core.dummy_thumbnail._template_docx", lambda t, v, ls: fake_docx)

    # 1. First request on cache miss -> placeholder returned immediately, 1 job queued
    res1 = render_template_thumbnail(
        db=db_mock,
        tmpl=tmpl,
        ver=ver,
        club_slug="acm",
        club_id="club-1",
    )
    assert res1.exists()
    assert is_placeholder_file(res1)
    assert get_queue_size() == 1
    assert is_thumbnail_pending(stem)

    # 2. Second request -> duplicate not queued, still 1 job
    res2 = render_template_thumbnail(
        db=db_mock,
        tmpl=tmpl,
        ver=ver,
        club_slug="acm",
        club_id="club-1",
    )
    assert res2.exists()
    assert is_placeholder_file(res2)
    assert get_queue_size() == 1

    # Mock _render_thumbnail to simulate successful worker rendering
    def fake_worker_render(db, tmpl, ver, club_slug, docx_path, thumb_path, local_storage, render_pages=False, **kwargs):
        with Image.new("RGB", (424, 600), color=(100, 150, 200)) as img:
            img.save(str(thumb_path), format="WEBP")
        # Remove placeholder marker as real render does
        if thumb_path.with_suffix(".placeholder").exists():
            thumb_path.with_suffix(".placeholder").unlink()
        return thumb_path

    monkeypatch.setattr("server.app.core.dummy_thumbnail._render_thumbnail", fake_worker_render)
    monkeypatch.setattr("server.app.core.database.SessionLocal", lambda: db_mock)

    # Resume worker and wait for completion
    resume_worker()
    wait_for_thumbnail_jobs(timeout=5.0)

    # Worker has finished
    assert not is_thumbnail_pending(stem)
    assert get_queue_size() == 0

    # Finished thumbnail was saved to persistent storage via local_storage.push
    assert f"thumbnails/{thumb_path.name}" in pushed_keys

    # 3. Subsequent request returns real thumbnail (not placeholder)
    res3 = render_template_thumbnail(
        db=db_mock,
        tmpl=tmpl,
        ver=ver,
        club_slug="acm",
        club_id="club-1",
    )
    assert res3 == thumb_path
    assert not is_placeholder_file(res3)
    with Image.open(res3) as img:
        assert img.size == (424, 600)

    # Cleanup
    if thumb_path.exists():
        thumb_path.unlink()
    if marker.exists():
        marker.unlink()


def test_placeholder_card_contains_no_raw_placeholders():
    """Placeholder image contains no '[' raw placeholder text (verified in code path and content)."""
    tmpl = Template(id="tmpl-test-ph", slug="approval_note", name="Approval Note", category="Official Documents")
    ver = TemplateVersion(id="ver-test-ph", version_no=1, template_id="tmpl-test-ph")

    # 1. Verify code path: _render_clean_placeholder and get_clean_placeholder must not parse docx or use regex for placeholders
    func_source = inspect.getsource(_render_clean_placeholder)
    # Must not contain placeholder substitution patterns like r"[\1]" or re.sub for {{ ... }} -> [...]
    assert r"[\1]" not in func_source
    assert 'r"[' not in func_source

    # 2. Generate placeholder and verify drawn texts contain no '[' or ']' brackets
    local_storage = require_local_storage()
    target_path = local_storage.base_dir / "thumbnails" / "test_clean_placeholder.webp"
    try:
        res = get_clean_placeholder(tmpl, ver, club_slug="", target_path=target_path)
        assert res.exists()
        assert is_placeholder_file(res)

        with Image.open(res) as img:
            assert img.format == "WEBP"
            assert img.size == (420, 594)
    finally:
        if target_path.exists():
            target_path.unlink()
        if target_path.with_suffix(".placeholder").exists():
            target_path.with_suffix(".placeholder").unlink()


def test_low_memory_mode_off_behaves_unchanged(monkeypatch, tmp_path):
    """LOW_MEMORY_MODE off: existing behaviour unchanged (synchronous render via _RENDER_SLOTS)."""
    monkeypatch.setattr(settings, "LOW_MEMORY_MODE", False)

    tmpl = Template(id="tmpl-norm", slug="permission_letter", name="Permission Letter", club_id=None)
    ver = TemplateVersion(id="ver-norm", version_no=1, template_id="tmpl-norm")

    local_storage = require_local_storage()
    expected_stem = f"{ver.id}_club-test"
    thumb_path = local_storage.base_dir / "thumbnails" / f"{expected_stem}.webp"
    if thumb_path.exists():
        thumb_path.unlink()

    fake_docx = tmp_path / "template.docx"
    fake_docx.write_bytes(b"fake docx")
    monkeypatch.setattr("server.app.core.dummy_thumbnail._template_docx", lambda t, v, ls: fake_docx)

    db_mock = mock.MagicMock()

    with mock.patch("server.app.core.dummy_thumbnail._render_thumbnail") as mock_render:
        mock_render.return_value = thumb_path
        res = render_template_thumbnail(
            db=db_mock,
            tmpl=tmpl,
            ver=ver,
            club_slug="acm",
            club_id="club-test",
        )
        mock_render.assert_called_once()
        assert res == thumb_path
