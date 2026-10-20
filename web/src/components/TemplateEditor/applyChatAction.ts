import type { Editor } from '@tiptap/core';
import type { Node as PMNode } from '@tiptap/pm/model';
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
import { themeDesignSettings } from './themes';

export interface ApplyChatActionParams {
  action: EditorAssistantAction;
  editor: Editor | null;
  fields?: TemplateField[];
  setTemplate: React.Dispatch<React.SetStateAction<any>>;
  setFields: React.Dispatch<React.SetStateAction<TemplateField[]>>;
  setDesignSettings: React.Dispatch<React.SetStateAction<DesignSettings>>;
  markUnsaved: () => void;
}

/** Outcome of applying one suggestion; `message` explains why it could not be applied. */
export interface ApplyResult {
  ok: boolean;
  message?: string;
}

const done: ApplyResult = { ok: true };
const fail = (message: string): ApplyResult => ({ ok: false, message });

type Found = { pos: number; node: PMNode };

/** A block by its blockId, anywhere in the document. */
function findBlock(editor: Editor, blockId?: string | null): Found | null {
  if (!blockId) return null;
  let found: Found | null = null;
  editor.state.doc.descendants((node, pos) => {
    if (found) return false;
    if (node.attrs?.blockId === blockId) {
      found = { pos, node };
      return false;
    }
    return true;
  });
  return found;
}

/** The text block (paragraph/heading) holding the cursor. */
function currentTextBlock(editor: Editor): Found | null {
  const { $from } = editor.state.selection;
  for (let d = $from.depth; d > 0; d--) {
    const node = $from.node(d);
    if (node.isTextblock) return { pos: $from.before(d), node };
  }
  return null;
}

/** The first top-level block of a type (e.g. the first repeating table). */
function firstBlock(editor: Editor, test: (n: PMNode) => boolean): Found | null {
  let found: Found | null = null;
  editor.state.doc.descendants((node, pos) => {
    if (found) return false;
    if (test(node)) {
      found = { pos, node };
      return false;
    }
    return true;
  });
  return found;
}

/** Exact text anywhere in one text block, as a document range. */
function findText(editor: Editor, text: string): { from: number; to: number } | null {
  const needle = text.trim();
  if (!needle) return null;
  let range: { from: number; to: number } | null = null;
  editor.state.doc.descendants((node, pos) => {
    if (range || !node.isTextblock) return !range;
    const content = node.textContent;
    const idx = content.indexOf(needle);
    if (idx === -1) return false;
    // Map the text offset to a document position (inline atoms such as field chips count as one)
    let offset = 0;
    let from = -1;
    let to = -1;
    node.forEach((child, childOffset) => {
      const len = child.isText ? child.text!.length : child.textContent.length;
      const start = offset;
      if (from === -1 && idx >= start && idx <= start + len && child.isText) from = pos + 1 + childOffset + (idx - start);
      const end = idx + needle.length;
      if (to === -1 && end >= start && end <= start + len && child.isText) to = pos + 1 + childOffset + (end - start);
      offset += len;
    });
    if (from !== -1 && to !== -1) range = { from, to };
    return false;
  });
  return range;
}

/** Replace a text block's words, keeping its type (heading stays a heading) and attributes. */
function replaceBlockText(editor: Editor, target: Found, text: string): void {
  const { state } = editor;
  const from = target.pos + 1;
  const to = target.pos + target.node.nodeSize - 1;
  const tr = state.tr.replaceWith(from, to, text ? state.schema.text(text) : []);
  editor.view.dispatch(tr);
}

function setBlockAttrs(editor: Editor, target: Found, attrs: Record<string, any>): void {
  const clean = Object.fromEntries(Object.entries(attrs).filter(([k]) => k in target.node.type.spec.attrs! || k in target.node.attrs));
  editor.view.dispatch(editor.state.tr.setNodeMarkup(target.pos, undefined, { ...target.node.attrs, ...clean }));
}

function insertAfter(editor: Editor, target: Found | null, nodeJSON: any): boolean {
  if (target) {
    const at = target.pos + target.node.nodeSize;
    try {
      editor.chain().focus().insertContentAt(at, nodeJSON).run();
      return true;
    } catch {
      // fall through to cursor
    }
  }
  return safeInsertBlock(editor, nodeJSON) !== false;
}

/** Column definitions of a repeating table, read back from its header and data rows. */
function repeatingColumns(table: PMNode): { key: string; label: string }[] {
  const header = table.child(0);
  const data = table.childCount > 1 ? table.child(1) : null;
  const listVar = table.attrs.listVariable || 'items';
  const cols: { key: string; label: string }[] = [];
  header.forEach((cell, _o, i) => {
    let key = '';
    if (data && i < data.childCount) {
      data.child(i).descendants((n) => {
        if (n.type.name === 'fieldChip' && !key) key = String(n.attrs.fieldName || '').replace(`${listVar}.`, '');
        return !key;
      });
    }
    const label = cell.textContent.trim() || `Column ${i + 1}`;
    cols.push({ key: key || label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || `col_${i + 1}`, label });
  });
  return cols;
}

function rebuildRepeatingTable(editor: Editor, target: Found, cols: { key: string; label: string }[], overrides: Record<string, any> = {}) {
  const a = { ...target.node.attrs, ...overrides };
  const node = createRepeatingTableNode(
    cols,
    a.listVariable || 'items',
    a.itemAlias || 'item',
    !!a.hasTotal,
    a.totalLabel || 'Total',
    a.totalVarName || `total_${a.listVariable || 'items'}_amount`
  ) as any;
  node.attrs = { ...node.attrs, blockId: target.node.attrs.blockId };
  editor
    .chain()
    .insertContentAt({ from: target.pos, to: target.pos + target.node.nodeSize }, node)
    .run();
}

const slug = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40) || 'new_column';

export function applyChatAction({
  action,
  editor,
  fields = [],
  setTemplate,
  setFields,
  setDesignSettings,
  markUnsaved,
}: ApplyChatActionParams): ApplyResult {
  if (!editor) return fail('The editor is not ready yet.');

  const type = action.type as string;
  const p = (action.payload || {}) as any;
  const applied = () => {
    markUnsaved();
    return done;
  };

  // ---------------- Template details ----------------
  if (type === 'set_title' || type === 'set_document_title') {
    if (!p.title) return fail('No title was suggested.');
    setTemplate((prev: any) => ({ ...prev, name: p.title }));
    return applied();
  }
  if (type === 'set_description' || type === 'set_document_description') {
    if (!p.description) return fail('No description was suggested.');
    setTemplate((prev: any) => ({ ...prev, description: p.description }));
    return applied();
  }

  // ---------------- Fields ----------------
  if (type === 'add_field' && p.field) {
    if (fields.some((f) => f.key === p.field.key)) return fail(`A field named "${p.field.key}" already exists.`);
    setFields((prev) => [...prev, p.field as TemplateField]);
    return applied();
  }
  if (type === 'rename_field' && p.old_key && p.new_key) {
    if (!fields.some((f) => f.key === p.old_key)) return fail(`There is no field "${p.old_key}".`);
    setFields((prev) => prev.map((f) => (f.key === p.old_key ? { ...f, key: p.new_key, label: p.new_label || f.label } : f)));
    // Chips in the document follow the rename
    const tr = editor.state.tr;
    editor.state.doc.descendants((node, pos) => {
      if (node.type.name === 'fieldChip' && node.attrs.fieldName === p.old_key) {
        tr.setNodeMarkup(pos, undefined, { ...node.attrs, fieldName: p.new_key, label: p.new_label || node.attrs.label });
      }
    });
    editor.view.dispatch(tr);
    return applied();
  }
  if (type === 'set_field_property' && p.key && p.property) {
    if (!fields.some((f) => f.key === p.key)) return fail(`There is no field "${p.key}".`);
    setFields((prev) => prev.map((f) => (f.key === p.key ? { ...f, [p.property]: p.value } : f)));
    return applied();
  }

  // ---------------- Page and theme ----------------
  if (type === 'set_theme' && p.theme) {
    const next = themeDesignSettings(p.theme);
    if (!next) return fail(`Unknown theme "${p.theme}".`);
    setDesignSettings((prev) => ({ ...prev, ...(next as Partial<DesignSettings>) }));
    return applied();
  }
  if (type === 'set_page') {
    const borderMap: Record<string, DesignSettings['pageBorder']> = { none: 'none', thin: 'single', single: 'single', double: 'double', ornamental: 'double' };
    setDesignSettings((prev) => ({
      ...prev,
      orientation: p.orientation || prev.orientation,
      margins: p.margins || prev.margins,
      watermark: p.watermark !== undefined ? String(p.watermark) : prev.watermark,
      pageBg: p.background || prev.pageBg,
      pageBorder: p.border ? borderMap[p.border] || prev.pageBorder : prev.pageBorder,
    }));
    return applied();
  }

  // ---------------- Blocks ----------------
  if (type === 'insert_block' || type === 'insert_signature_grid') {
    const raw = (p.block || p) as any;
    if (!raw?.type) return fail('No block was suggested.');
    let node = raw;
    if (raw.type === 'signatureGrid') {
      const signs = raw.attrs?.signatures || raw.signatures || [];
      node = createSignatureGridNode(raw.attrs?.columns || raw.columns || (signs.length || 2), signs);
    } else if (raw.type === 'infoTable') {
      node = createInfoTableNode(raw.attrs?.rows || raw.rows);
    } else if (raw.type === 'repeatingTable') {
      const listVar = raw.attrs?.listVariable || raw.listVariable || 'items';
      node = createRepeatingTableNode(
        raw.attrs?.columns || raw.columns || [],
        listVar,
        raw.attrs?.itemAlias || raw.itemAlias || 'item',
        raw.attrs?.hasTotal ?? raw.hasTotal ?? true,
        raw.attrs?.totalLabel || raw.totalLabel || 'Total',
        raw.attrs?.totalVarName || raw.totalVarName || `total_${listVar}_amount`
      );
    } else if (raw.type === 'image' || raw.type === 'logo' || raw.type === 'clubLogo') {
      node = createImageBlockNode({ ...(raw.attrs || {}), imageType: raw.type === 'image' ? 'image' : 'club-logo' });
    }
    const pos = p.position;
    if (pos === 'start') {
      editor.chain().focus().insertContentAt(0, node).run();
      return applied();
    }
    if (pos === 'end') {
      editor.chain().focus().insertContentAt(editor.state.doc.content.size, node).run();
      return applied();
    }
    const after = typeof pos === 'object' && pos ? findBlock(editor, pos.after || pos.block_id) : null;
    return insertAfter(editor, after, node) ? applied() : fail('The block could not be inserted here.');
  }

  if (type === 'delete_block') {
    const target = findBlock(editor, p.block_id);
    if (!target) return fail('That block is no longer in the document.');
    editor.chain().deleteRange({ from: target.pos, to: target.pos + target.node.nodeSize }).run();
    return applied();
  }

  if (type === 'duplicate_block') {
    const target = findBlock(editor, p.block_id);
    if (!target) return fail('That block is no longer in the document.');
    const copy = target.node.toJSON();
    if (copy.attrs) delete copy.attrs.blockId; // a fresh id is assigned on insert
    editor.chain().insertContentAt(target.pos + target.node.nodeSize, copy).run();
    return applied();
  }

  if (type === 'move_block') {
    const source = findBlock(editor, p.block_id);
    const dest = findBlock(editor, p.target_block_id);
    if (!source || !dest) return fail('One of those blocks is no longer in the document.');
    if (source.pos === dest.pos) return done;
    const json = source.node.toJSON();
    const tr = editor.state.tr.delete(source.pos, source.pos + source.node.nodeSize);
    const destPos = tr.mapping.map(p.position === 'after' ? dest.pos + dest.node.nodeSize : dest.pos);
    tr.insert(destPos, editor.state.schema.nodeFromJSON(json));
    editor.view.dispatch(tr);
    return applied();
  }

  if (type === 'update_block') {
    const target = findBlock(editor, p.block_id);
    if (!target) return fail('That block is no longer in the document.');
    const { text, ...attrs } = (p.attrs || {}) as Record<string, any>;
    if (typeof text === 'string' && text.trim()) {
      if (!target.node.isTextblock) return fail('Only paragraphs and headings can be reworded.');
      replaceBlockText(editor, target, text);
    }
    const fresh = findBlock(editor, p.block_id) || target;
    const styleAttrs = Object.fromEntries(Object.entries(attrs).filter(([k]) => k !== 'blockId'));
    if (Object.keys(styleAttrs).length) setBlockAttrs(editor, fresh, styleAttrs);
    return applied();
  }

  // ---------------- Styling ----------------
  if (type === 'set_text_style') {
    const target = findBlock(editor, p.block_id) || currentTextBlock(editor) || firstBlock(editor, (n) => n.type.name === 'heading');
    if (!target || !target.node.isTextblock) return fail('Click into the text you want to style, then apply again.');
    const attrs: Record<string, any> = {};
    if (p.alignment) attrs.textAlign = p.alignment;
    if (p.color) attrs.textColor = p.color;
    if (p.size) attrs.fontSize = String(p.size).replace(/(px|rem)$/, '');
    if (p.font) attrs.fontFamily = p.font;
    if (p.highlight) attrs.backgroundColor = p.highlight;
    if (Object.keys(attrs).length) setBlockAttrs(editor, target, attrs);
    const fresh = findBlock(editor, target.node.attrs.blockId) || target;
    const from = fresh.pos + 1;
    const to = fresh.pos + fresh.node.nodeSize - 1;
    const chain = editor.chain().setTextSelection({ from, to }) as any;
    if (p.bold !== undefined) (p.bold ? chain.setBold() : chain.unsetBold());
    if (p.italic !== undefined) (p.italic ? chain.setItalic() : chain.unsetItalic());
    if (p.underline !== undefined) (p.underline ? chain.setUnderline() : chain.unsetUnderline());
    chain.setTextSelection(to).run();
    return applied();
  }

  if (type === 'set_block_style') {
    const target = findBlock(editor, p.block_id) || currentTextBlock(editor);
    if (!target) return fail('Click into the block you want to style, then apply again.');
    const bg = p.background || p.shading;
    if (!bg) return fail('Only a background colour can be set on a block.');
    if (!target.node.isTextblock) return fail('A background can only be set on a paragraph or heading.');
    setBlockAttrs(editor, target, { backgroundColor: bg });
    return applied();
  }

  // ---------------- Fields in text ----------------
  if (type === 'insert_chip' && (p.field_key || p.field_name)) {
    const key = p.field_name || p.field_key;
    let field = fields.find((f) => f.key === key);
    if (!field) {
      field = { key, label: key.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()), type: 'text', required: false } as TemplateField;
      setFields((prev) => [...prev, field!]);
    }
    const target = findBlock(editor, p.block_id);
    const position = target && target.node.isTextblock ? target.pos + target.node.nodeSize - 1 : undefined;
    insertFieldChip(editor, key, field.label || key, field.type || 'text', field.ask || '', 'optional', !!field.required, !!field.sensitive, position);
    return applied();
  }

  if (type === 'insert_clause') {
    const text = p.text || '';
    if (!text.trim()) return fail('The clause has no text.');
    insertAfter(editor, findBlock(editor, p.block_id), { type: 'paragraph', attrs: { ai_suggested: true }, content: [{ type: 'text', text }] });
    return applied();
  }

  // ---------------- Logo ----------------
  if (type === 'set_letterhead' || type === 'update_logo') {
    const align = ['left', 'center', 'right'].includes(p.align) ? p.align : 'center';
    const existing = firstBlock(editor, (n) => n.type.name === 'imageBlock' && ['club-logo', 'logo'].includes(n.attrs.imageType));
    const assetAttrs = p.asset_id ? { clubLogoAssetId: p.asset_id, logoAssetId: p.asset_id, assetId: p.asset_id } : {};
    if (existing) {
      setBlockAttrs(editor, existing, { placement: align, ...assetAttrs });
    } else {
      // An empty club-logo block prints the club's own logo
      editor
        .chain()
        .focus()
        .insertContentAt(0, createImageBlockNode({ imageType: 'club-logo', placement: align, width: '120px', ...assetAttrs } as any))
        .run();
    }
    return applied();
  }

  // ---------------- Rewording ----------------
  if (type === 'rewrite_text' || type === 'rewrite_selected_text' || type === 'translate_text' || type === 'proofread_text') {
    const text = String(p.text || '');
    if (!text.trim()) return fail('No new wording was suggested.');
    if (!editor.state.selection.empty) {
      editor.chain().focus().deleteSelection().insertContent(text).run();
      return applied();
    }
    const range = p.original_text ? findText(editor, p.original_text) : null;
    if (range) {
      editor.chain().focus().insertContentAt(range, text).run();
      return applied();
    }
    const target = findBlock(editor, p.block_id);
    if (target && target.node.isTextblock) {
      replaceBlockText(editor, target, text);
      return applied();
    }
    // Nothing to replace: add the wording as a new paragraph after the cursor
    safeInsertBlock(editor, { type: 'paragraph', attrs: { ai_suggested: true }, content: [{ type: 'text', text }] });
    return applied();
  }

  // ---------------- Tables ----------------
  const tableTarget = (): Found | null =>
    findBlock(editor, p.block_id) ||
    (() => {
      const { $from } = editor.state.selection;
      for (let d = $from.depth; d > 0; d--) {
        if ($from.node(d).type.name === 'table') return { pos: $from.before(d), node: $from.node(d) };
      }
      return null;
    })() ||
    firstBlock(editor, (n) => n.type.name === 'table' && n.attrs.blockType !== 'signatureGrid');

  if (type === 'add_table_column') {
    const target = tableTarget();
    if (!target || target.node.type.name !== 'table') return fail('There is no table to add a column to.');
    const name = p.column_name || 'New Column';
    if (target.node.attrs.blockType === 'repeatingTable') {
      const cols = repeatingColumns(target.node);
      rebuildRepeatingTable(editor, target, [...cols, { key: slug(name), label: name }]);
      return applied();
    }
    // Plain/info tables: add a column after the last cell and title it
    const lastCellPos = target.pos + target.node.nodeSize - 3;
    (editor.chain().setTextSelection(lastCellPos) as any).addColumnAfter().run();
    return applied();
  }

  if (type === 'add_table_row') {
    const target = tableTarget();
    if (!target || target.node.type.name !== 'table') return fail('There is no table to add a row to.');
    if (target.node.attrs.blockType === 'repeatingTable') {
      return fail('Rows of this table come from the data entered when a document is created.');
    }
    const values: string[] = (p.values || []).map((v: any) => String(v ?? ''));
    const colCount = target.node.child(0).childCount;
    const row = {
      type: 'tableRow',
      content: Array.from({ length: colCount }, (_, i) => ({
        type: 'tableCell',
        content: [{ type: 'paragraph', content: values[i] ? [{ type: 'text', text: values[i] }] : [] }],
      })),
    };
    editor.chain().insertContentAt(target.pos + target.node.nodeSize - 1, row).run();
    return applied();
  }

  if (type === 'set_table_total') {
    const target = tableTarget();
    if (!target || target.node.attrs.blockType !== 'repeatingTable') return fail('Totals can only be added to an item table.');
    const cols = repeatingColumns(target.node);
    rebuildRepeatingTable(editor, target, cols, {
      hasTotal: p.enabled !== false,
      totalLabel: p.total_label || target.node.attrs.totalLabel || 'Total',
      totalVarName: p.total_var || target.node.attrs.totalVarName,
    });
    return applied();
  }

  if (type === 'ask_clarifying_question') return done;
  return fail(`This kind of change ("${type}") cannot be applied in the editor.`);
}
