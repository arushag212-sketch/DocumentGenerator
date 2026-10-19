"""Club-scoped editor assistant API.

This module intentionally is not imported into ``api/v1/__init__.py`` here:
the integration owner must add that one router include explicitly.  Keeping
the import hook visible makes the feature easy to enable without changing the
existing router bundle in a delegated task.
"""

from __future__ import annotations

import copy
import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.app.core.database import get_db
from server.app.core.editor_assistant import (
    EditorAssistantDocumentContext,
    EditorAssistantRequest,
    EditorAssistantResponse,
    assistant_prompt_hash,
    create_assistant_response,
)
from server.app.core.permissions import ClubContext, Role, require_club_access
from server.app.models import AIRequest, Template, TemplateVersion
from docgen.llm import LLMClient, get_llm_client


router = APIRouter(prefix="/clubs/{club_id}", tags=["editor-assistant"])


def _template_context(template: Template, version: TemplateVersion | None) -> EditorAssistantDocumentContext:
    """Build a non-sensitive context snapshot from a club-owned draft."""

    fields: list[dict[str, object]] = []
    if version and version.schema_yaml:
        try:
            parsed = yaml.safe_load(version.schema_yaml)
            for field in (parsed or {}).get("fields", []) if isinstance(parsed, dict) else []:
                if isinstance(field, dict):
                    fields.append(
                        {
                            "key": field.get("key"),
                            "label": field.get("ask") or field.get("key"),
                            "type": field.get("type", "text"),
                            "required": bool(field.get("required", False)),
                        }
                    )
        except Exception:
            fields = []

    blocks: list[dict[str, object]] = []
    editor_json = version.editor_json if version else None
    if isinstance(editor_json, dict):
        for block in editor_json.get("content", [])[:60]:
            if isinstance(block, dict):
                blocks.append({"type": block.get("type", "paragraph")})

    return EditorAssistantDocumentContext(
        title=template.name,
        description=template.description or "",
        fields=fields,
        blocks=blocks,
    )


def _resolve_template(
    template_id: str,
    ctx: ClubContext,
    db: Session,
) -> tuple[Template, TemplateVersion | None]:
    """Resolve only the active club's editable template."""

    template = db.query(Template).filter((Template.id == template_id) | (Template.slug == template_id)).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates are read-only. Fork the template before using editor actions.",
        )
    if template.club_id != ctx.club.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Template belongs to another club")
    version = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == template.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )
    return template, version


def _record_usage(
    response: EditorAssistantResponse,
    request: EditorAssistantRequest,
    ctx: ClubContext,
    db: Session,
    client: LLMClient,
) -> None:
    """Record model metadata only; never persist the chat prompt or document text."""

    if response.source != "gemini":
        return
    usage = getattr(client, "last_usage_metadata", None) or {}
    tokens_in = usage.get("tokens_in") or usage.get("promptTokenCount")
    tokens_out = usage.get("tokens_out") or usage.get("candidatesTokenCount")
    db.add(
        AIRequest(
            club_id=ctx.club.id,
            user_id=ctx.user.id,
            purpose="editor_assistant",
            model=client.model_name,
            prompt_hash=assistant_prompt_hash(request.instruction or request.message or "", request.selected_text),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            usage_estimated=bool(usage.get("usage_estimated", tokens_in is None or tokens_out is None)),
        )
    )


def _run_assistant(
    payload: EditorAssistantRequest,
    ctx: ClubContext,
    db: Session,
    template_id: str | None = None,
) -> EditorAssistantResponse:
    context = copy.deepcopy(payload.document_context)
    if template_id:
        template, version = _resolve_template(template_id, ctx, db)
        stored_context = _template_context(template, version)
        # Client metadata can include the current unsaved title/description;
        # stored fields and block summaries remain authoritative for safety.
        context = EditorAssistantDocumentContext(
            title=context.title or stored_context.title,
            description=context.description if context.description is not None else stored_context.description,
            fields=stored_context.fields,
            blocks=stored_context.blocks,
        )

    client = get_llm_client()
    response = create_assistant_response(
        instruction=payload.instruction or payload.message or "",
        selected_text=payload.selected_text,
        document_context=context,
        llm_client=client,
    )
    _record_usage(response, payload, ctx, db, client)
    return response


@router.post("/editor-assistant", response_model=EditorAssistantResponse)
def editor_assistant(
    payload: EditorAssistantRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> EditorAssistantResponse:
    """Return beginner-friendly, reviewable actions without mutating a draft."""

    return _run_assistant(payload, ctx, db)


@router.post("/documents/templates/{template_id}/assistant", response_model=EditorAssistantResponse)
@router.post("/documents/templates/{template_id}/editor-assistant", response_model=EditorAssistantResponse, include_in_schema=False)
def template_editor_assistant(
    template_id: str,
    payload: EditorAssistantRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> EditorAssistantResponse:
    """Return actions using a club-owned template's metadata as context."""

    return _run_assistant(payload, ctx, db, template_id=template_id)
