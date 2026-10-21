"""Club-scoped editor assistant API."""

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
from server.app.core.rate_limit import check_rate_limit
from server.app.models import AIRequest, Asset, Template, TemplateVersion
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
                b_type = block.get("type", "paragraph")
                b_id = (block.get("attrs") or {}).get("blockId")
                first_text = ""
                content = block.get("content") or []
                if isinstance(content, list) and content and isinstance(content[0], dict):
                    first_text = str(content[0].get("text") or "")[:80]
                blocks.append({"type": b_type, "blockId": b_id, "text": first_text})

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
    db.commit()


def _run_assistant(
    payload: EditorAssistantRequest,
    ctx: ClubContext,
    db: Session,
    template_id: str | None = None,
) -> EditorAssistantResponse:
    # Rate limits per user and per club
    check_rate_limit(f"editor_ai_user:{ctx.user.id}", max_requests=60, window_seconds=60, db=db)
    check_rate_limit(f"editor_ai_club:{ctx.club.id}", max_requests=120, window_seconds=60, db=db)

    context = copy.deepcopy(payload.document_context)
    if template_id:
        template, version = _resolve_template(template_id, ctx, db)
        stored_context = _template_context(template, version)
        context = EditorAssistantDocumentContext(
            title=context.title or stored_context.title,
            description=context.description if context.description is not None else stored_context.description,
            fields=stored_context.fields if not context.fields else context.fields,
            blocks=stored_context.blocks if not context.blocks else context.blocks,
            theme=context.theme,
            selected_block_id=context.selected_block_id,
        )

    client = get_llm_client()
    response = create_assistant_response(
        instruction=payload.instruction or payload.message or "",
        selected_text=payload.selected_text,
        document_context=context,
        llm_client=client,
    )

    # Validate asset ownership: drop any action that targets an asset owned by another club
    validated_actions = []
    for action in response.actions:
        p_data = action.payload or {}
        asset_id = p_data.get("asset_id") or (p_data.get("logo") or {}).get("asset_id")
        if asset_id:
            asset = db.query(Asset).filter(Asset.id == asset_id).first()
            if not asset or (asset.club_id is not None and asset.club_id != ctx.club.id):
                response.warnings.append(f"Action '{action.summary}' was rejected: asset not accessible to this club.")
                continue
        validated_actions.append(action)
    response.actions = validated_actions

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
