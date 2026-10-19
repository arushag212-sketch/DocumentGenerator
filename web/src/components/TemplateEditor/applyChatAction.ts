import type { Editor } from '@tiptap/core';
import type { EditorAssistantAction } from '../editorAssistant';
import type { TemplateField } from './FieldsPanel';
import type { DesignSettings } from './DesignPanel';
import {
  createSignatureGridNode,
  createInfoTableNode,
  createRepeatingTableNode,
} from './tableExtensions';
import { createImageBlockNode } from './imageBlock';
import { safeInsertBlock, insertFieldChip } from './extensions';

export interface ApplyChatActionParams {
  action: EditorAssistantAction;
  editor: Editor | null;
  setTemplate: React.Dispatch<React.SetStateAction<any>>;
  setFields: React.Dispatch<React.SetStateAction<TemplateField[]>>;
  setDesignSettings: React.Dispatch<React.SetStateAction<DesignSettings>>;
  markUnsaved: () => void;
}

export function applyChatAction({
  action,
  editor,
  setTemplate,
  setFields,
  setDesignSettings,
  markUnsaved,
}: ApplyChatActionParams): void {
  if (!editor) return;

  const { type, payload } = action;

  // Title & description
  if (type === 'set_title' || type === 'set_document_title') {
    if (payload.title) {
      setTemplate((prev: any) => ({ ...prev, name: payload.title }));
      markUnsaved();
    }
    return;
  }
  if (type === 'set_description' || type === 'set_document_description') {
    if (payload.description) {
      setTemplate((prev: any) => ({ ...prev, description: payload.description }));
      markUnsaved();
    }
    return;
  }

  // Field operations
  if (type === 'add_field' && payload.field) {
    setFields((prev) => [...prev, payload.field as TemplateField]);
    markUnsaved();
    return;
  }
  if (type === 'rename_field' && payload.old_key && payload.new_key) {
    setFields((prev) =>
      prev.map((f) =>
        f.key === payload.old_key
          ? { ...f, key: payload.new_key!, label: payload.new_label || f.label }
          : f
      )
    );
    markUnsaved();
    return;
  }
  if (type === 'set_field_property' && payload.key && payload.property) {
    setFields((prev) =>
      prev.map((f) =>
        f.key === payload.key ? { ...f, [payload.property!]: payload.value } : f
      )
    );
    markUnsaved();
    return;
  }

  // Theme & Design operations
  if (type === 'set_theme' && payload.theme) {
    setDesignSettings((prev) => ({ ...prev, theme: payload.theme! }));
    markUnsaved();
    return;
  }
  if (type === 'set_page') {
    setDesignSettings((prev) => ({
      ...prev,
      orientation: (payload.orientation as any) || prev.orientation,
      margins: (payload.margins as any) || prev.margins,
      watermark: payload.watermark !== undefined ? String(payload.watermark) : prev.watermark,
    }));
    markUnsaved();
    return;
  }

  // Editor block mutations in a single transaction
  editor.chain().focus();

  if (
    (type === 'insert_block' || (type as string) === 'insert_signature_grid') &&
    (payload.block || (payload as any).type)
  ) {
    const raw = (payload.block || payload) as any;
    let blockToInsert = raw;
    if (raw.type === 'signatureGrid') {
      const signs = raw.attrs?.signatures || raw.signatures || [];
      const count = raw.attrs?.columns || raw.columns || (signs.length > 0 ? signs.length : 2);
      blockToInsert = createSignatureGridNode(count, signs);
    } else if (raw.type === 'infoTable') {
      const rows = raw.attrs?.rows || raw.rows;
      blockToInsert = createInfoTableNode(rows);
    } else if (raw.type === 'repeatingTable') {
      const cols = raw.attrs?.columns || raw.columns || [];
      const listVar = raw.attrs?.listVariable || raw.listVariable || 'items';
      const itemAlias = raw.attrs?.itemAlias || raw.itemAlias || 'item';
      const hasTotal = raw.attrs?.hasTotal ?? raw.hasTotal ?? true;
      const totalLabel = raw.attrs?.totalLabel || raw.totalLabel || 'Total';
      const totalVar = raw.attrs?.totalVarName || raw.totalVarName || `total_${listVar}_amount`;
      blockToInsert = createRepeatingTableNode(cols, listVar, itemAlias, hasTotal, totalLabel, totalVar);
    } else if (raw.type === 'image' || raw.type === 'logo' || raw.type === 'clubLogo') {
      blockToInsert = createImageBlockNode(raw.attrs || {});
    }

    safeInsertBlock(editor, blockToInsert);
    markUnsaved();
    return;
  }

  if (type === 'insert_chip' && (payload.field_key || (payload as any).field_name)) {
    const fn = (payload as any).field_name || payload.field_key;
    const lbl = (payload as any).label || fn;
    insertFieldChip(editor, fn, lbl);
    markUnsaved();
    return;
  }

  if (type === 'set_block_style') {
    if (payload.alignment) {
      editor.commands.setTextAlign(payload.alignment);
    }
    markUnsaved();
    return;
  }

  if (type === 'insert_clause') {
    const text = payload.text || 'Standard Club Undertaking Clause';
    editor.chain().insertContent({ type: 'paragraph', content: [{ type: 'text', text }] }).run();
    markUnsaved();
    return;
  }

  if (type === 'set_letterhead' || type === 'update_logo') {
    editor.chain().insertContent({
      type: 'paragraph',
      attrs: { textAlign: payload.align || 'left' },
      content: [{ type: 'text', text: `[Club Logo: ${payload.instruction || 'Official'}]` }],
    }).run();
    markUnsaved();
    return;
  }

  if (type === 'set_text_style') {
    let targetPos: number | null = null;
    editor.state.doc.descendants((node, pos) => {
      if (node.type.name === 'heading' && targetPos === null) {
        targetPos = pos;
      }
    });

    if (targetPos !== null) {
      editor.commands.setNodeSelection(targetPos);
      if (payload.alignment) {
        editor.commands.setTextAlign(payload.alignment);
      }
      editor.commands.updateAttributes('heading', {
        textAlign: payload.alignment || undefined,
        color: payload.color || undefined,
      });
    } else {
      if (payload.alignment) editor.commands.setTextAlign(payload.alignment);
    }
    markUnsaved();
    return;
  }

  if (
    type === 'rewrite_text' ||
    type === 'rewrite_selected_text' ||
    type === 'translate_text' ||
    type === 'proofread_text'
  ) {
    const textToInsert = payload.text || '';
    if (!editor.state.selection.empty) {
      editor.chain().deleteSelection().insertContent(textToInsert).run();
    } else {
      editor.chain().insertContent({ type: 'paragraph', content: [{ type: 'text', text: textToInsert }] }).run();
    }
    markUnsaved();
    return;
  }

  if (type === 'delete_block' && payload.block_id) {
    let deletePos: number | null = null;
    let deleteNodeSize = 0;
    editor.state.doc.descendants((node, pos) => {
      if (node.attrs?.blockId === payload.block_id && deletePos === null) {
        deletePos = pos;
        deleteNodeSize = node.nodeSize;
      }
    });
    if (deletePos !== null && deleteNodeSize > 0) {
      (editor.chain() as any).deleteRange({ from: deletePos, to: deletePos + deleteNodeSize }).run();
      markUnsaved();
    }
    return;
  }

  if (type === 'update_block' && (payload as any).block_id) {
    const targetBlockId = (payload as any).block_id;
    let targetPos: number | null = null;
    let targetNodeSize = 0;
    editor.state.doc.descendants((node, pos) => {
      if (node.attrs?.blockId === targetBlockId && targetPos === null) {
        targetPos = pos;
        targetNodeSize = node.nodeSize;
      }
    });
    if (targetPos !== null && targetNodeSize > 0) {
      const newText = (payload as any).text || '';
      (editor.chain() as any)
        .deleteRange({ from: targetPos, to: targetPos + targetNodeSize })
        .insertContentAt(targetPos, {
          type: 'paragraph',
          attrs: { blockId: targetBlockId },
          content: newText ? [{ type: 'text', text: newText }] : [],
        })
        .run();
      markUnsaved();
    }
    return;
  }

  if (type === 'add_table_column') {
    (editor.chain() as any).addColumnAfter?.()?.run?.();
    markUnsaved();
    return;
  }
  if (type === 'add_table_row') {
    (editor.chain() as any).addRowAfter?.()?.run?.();
    markUnsaved();
    return;
  }
}
