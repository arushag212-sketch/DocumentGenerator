"""Unit tests for Phase 2: TipTap editable tables migration and DOCX compilation."""

import pytest
from server.app.core.template_compiler import (
    migrate_template_content,
    TipTapDocxCompiler,
    validate_template_identifiers,
)


def test_migrate_template_content_info_table():
    legacy_json = {
        "type": "doc",
        "content": [
            {
                "type": "infoTable",
                "attrs": {
                    "rows": [
                        {"label": "Event Title", "field": "event_name"},
                        {"label": "Date", "field": "event_date"},
                    ]
                },
            }
        ],
    }

    migrated = migrate_template_content(legacy_json)
    blocks = migrated["content"]
    assert len(blocks) == 1
    table_block = blocks[0]
    assert table_block["type"] == "table"
    assert table_block["attrs"]["blockType"] == "infoTable"
    assert len(table_block["content"]) == 2

    # Row 0
    row0 = table_block["content"][0]
    assert row0["type"] == "tableRow"
    assert len(row0["content"]) == 2
    c0 = row0["content"][0]
    c1 = row0["content"][1]
    assert c0["content"][0]["content"][0]["text"] == "Event Title"
    assert c1["content"][0]["content"][0]["type"] == "fieldChip"
    assert c1["content"][0]["content"][0]["attrs"]["fieldName"] == "event_name"


def test_migrate_template_content_repeating_table():
    legacy_json = {
        "type": "doc",
        "content": [
            {
                "type": "repeatingTable",
                "attrs": {
                    "listVariable": "budget_items",
                    "itemAlias": "item",
                    "columns": [
                        {"key": "desc", "label": "Description"},
                        {"key": "cost", "label": "Cost (INR)"},
                    ],
                    "hasTotal": True,
                    "totalLabel": "Total Budget",
                    "totalVarName": "total_budget_amount",
                },
            }
        ],
    }

    migrated = migrate_template_content(legacy_json)
    blocks = migrated["content"]
    assert len(blocks) == 1
    table_block = blocks[0]
    assert table_block["type"] == "table"
    assert table_block["attrs"]["blockType"] == "repeatingTable"
    assert table_block["attrs"]["listVariable"] == "budget_items"
    assert len(table_block["content"]) == 3  # Header, Data, Total


def test_migrate_template_content_signature_grid():
    legacy_json = {
        "type": "doc",
        "content": [
            {
                "type": "signatureGrid",
                "attrs": {
                    "columns": 2,
                    "signatures": [
                        {"label": "Chairperson", "designation": "ACM Chapter"},
                        {"label": "Faculty Advisor", "designation": "DoCSE"},
                    ],
                },
            }
        ],
    }

    migrated = migrate_template_content(legacy_json)
    blocks = migrated["content"]
    assert len(blocks) == 1
    table_block = blocks[0]
    assert table_block["type"] == "table"
    assert table_block["attrs"]["blockType"] == "signatureGrid"
    row0 = table_block["content"][0]
    assert len(row0["content"]) == 2
    assert row0["content"][0]["content"][0]["content"][0]["text"] == "Chairperson"


def test_tiptap_compiler_renders_native_tables():
    """Verify TipTapDocxCompiler constructs valid python-docx Document from native tables."""
    native_json = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 1},
                "content": [{"type": "text", "text": "Annual Tech Symposium Approval"}],
            },
            {
                "type": "table",
                "attrs": {"blockType": "infoTable", "class": "cd-info-table"},
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Event Name"}]}],
                            },
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {"type": "fieldChip", "attrs": {"fieldName": "event_name", "label": "event_name"}}
                                        ],
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
            {
                "type": "table",
                "attrs": {
                    "blockType": "repeatingTable",
                    "class": "cd-repeating-table",
                    "listVariable": "budget_items",
                    "itemAlias": "item",
                    "hasTotal": True,
                    "totalLabel": "Total Budget",
                    "totalVarName": "total_budget_amount",
                },
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableHeader",
                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Item"}]}],
                            },
                            {
                                "type": "tableHeader",
                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Amount"}]}],
                            },
                        ],
                    },
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {"type": "fieldChip", "attrs": {"fieldName": "budget_items.item", "label": "item"}}
                                        ],
                                    }
                                ],
                            },
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {"type": "fieldChip", "attrs": {"fieldName": "budget_items.amount", "label": "amount"}}
                                        ],
                                    }
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "type": "table",
                "attrs": {"blockType": "signatureGrid", "class": "cd-signature-grid", "columns": 2},
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "Student Chairperson"}]},
                                    {"type": "paragraph", "content": [{"type": "text", "text": "ACM Chapter"}]},
                                ],
                            },
                            {
                                "type": "tableCell",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "Faculty Advisor"}]},
                                    {"type": "paragraph", "content": [{"type": "text", "text": "SVNIT Surat"}]},
                                ],
                            },
                        ],
                    }
                ],
            },
        ],
    }

    fields = [
        {"key": "event_name", "label": "Event Name", "type": "text"},
        {
            "key": "budget_items",
            "label": "Budget Items",
            "type": "table",
            "columns": [{"key": "item", "type": "text"}, {"key": "amount", "type": "money"}],
        },
    ]

    validate_template_identifiers(native_json, fields)

    compiler = TipTapDocxCompiler(editor_json=native_json, fields=fields, club_slug="acm")
    doc = compiler.build()

    assert doc is not None
    # 1 header table + 3 content tables
    assert len(doc.tables) >= 3
