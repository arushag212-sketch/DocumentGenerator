import { Node, Extension, mergeAttributes } from '@tiptap/core';
import { BlockIdExtension, ensureBlockIds } from './blockId';
import {
  CustomTable,
  CustomTableRow,
  CustomTableCell,
  CustomTableHeader,
  createInfoTableNode,
  createRepeatingTableNode,
  createSignatureGridNode,
} from './tableExtensions';
import {
  ImageBlock,
  createImageBlockNode,
  type ImageBlockAttributes,
} from './imageBlock';

export {
  BlockIdExtension,
  ensureBlockIds,
  CustomTable,
  CustomTableRow,
  CustomTableCell,
  CustomTableHeader,
  createInfoTableNode,
  createRepeatingTableNode,
  createSignatureGridNode,
  ImageBlock,
  createImageBlockNode,
  type ImageBlockAttributes,
};

export const AiSuggestedBlock = Extension.create({
  name: 'aiSuggestedBlock',
  addGlobalAttributes() {
    return [
      {
        types: ['heading', 'paragraph'],
        attributes: {
          ai_suggested: {
            default: false,
            parseHTML: (element: any) => element.getAttribute('data-ai-suggested') === 'true',
            renderHTML: (attributes: any) => {
              if (!attributes.ai_suggested) return {};
              return { 'data-ai-suggested': 'true' };
            },
          },
          official_wording_required: {
            default: false,
            parseHTML: (element: any) => element.getAttribute('data-official-wording') === 'true',
            renderHTML: (attributes: any) => {
              if (!attributes.official_wording_required) return {};
              return { 'data-official-wording': 'true' };
            },
          },
          // Per-block style (set from the toolbar or the AI copilot); the compiler prints the same
          textColor: {
            default: null,
            parseHTML: (element: any) => element.getAttribute('data-text-color'),
            renderHTML: (attributes: any) =>
              attributes.textColor ? { 'data-text-color': attributes.textColor, style: `color: ${attributes.textColor}` } : {},
          },
          fontSize: {
            default: null,
            parseHTML: (element: any) => element.getAttribute('data-font-size'),
            renderHTML: (attributes: any) =>
              attributes.fontSize
                ? { 'data-font-size': attributes.fontSize, style: `font-size: ${String(attributes.fontSize).replace(/pt$/, '')}pt` }
                : {},
          },
          fontFamily: {
            default: null,
            parseHTML: (element: any) => element.getAttribute('data-font-family'),
            renderHTML: (attributes: any) =>
              attributes.fontFamily ? { 'data-font-family': attributes.fontFamily, style: `font-family: "${attributes.fontFamily}"` } : {},
          },
          backgroundColor: {
            default: null,
            parseHTML: (element: any) => element.getAttribute('data-bg-color'),
            renderHTML: (attributes: any) =>
              attributes.backgroundColor
                ? { 'data-bg-color': attributes.backgroundColor, style: `background-color: ${attributes.backgroundColor}; padding: 2px 4px` }
                : {},
          },
        },
      },
    ];
  },
});

export const FieldChip = Node.create({
  name: 'fieldChip',
  group: 'inline',
  inline: true,
  atom: true,
  isolating: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      fieldName: { default: '' },
      label: { default: '' },
      fieldType: { default: 'text' },
      ask: { default: '' },
      importance: { default: 'optional' },
      required: { default: false },
      sensitive: { default: false },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-field-name]',
        getAttrs: (element) => {
          const el = element as HTMLElement;
          const imp = el.getAttribute('data-importance') || (el.getAttribute('data-required') === 'true' ? 'essential' : 'optional');
          return {
            fieldName: el.getAttribute('data-field-name') || '',
            label: el.getAttribute('data-label') || el.getAttribute('data-field-name') || '',
            fieldType: el.getAttribute('data-field-type') || 'text',
            ask: el.getAttribute('data-ask') || '',
            importance: imp,
            required: imp === 'essential' || el.getAttribute('data-required') === 'true',
            sensitive: el.getAttribute('data-sensitive') === 'true',
          };
        },
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    const fieldName = HTMLAttributes.fieldName || '';
    const label = HTMLAttributes.label || fieldName;
    const importance = HTMLAttributes.importance || (HTMLAttributes.required ? 'essential' : 'optional');
    const badgeText = importance === 'essential' ? 'Essential' : 'Optional';
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-field-name': fieldName,
        'data-label': label,
        'data-field-type': HTMLAttributes.fieldType || 'text',
        'data-importance': importance,
        'data-required': importance === 'essential' ? 'true' : 'false',
        'data-sensitive': HTMLAttributes.sensitive ? 'true' : 'false',
        'data-ask': HTMLAttributes.ask || '',
        role: 'button',
        tabindex: '0',
        title: `Dynamic field: ${label}`,
        class:
          'field-chip inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-900 border border-indigo-300 shadow-sm mx-1 cursor-pointer select-none hover:bg-indigo-100',
      }),
      `⚡ ${label}`,
      [
        'span',
        {
          class: `text-[9px] px-1.5 py-0.2 rounded-full font-bold uppercase tracking-wider ml-1 ${
            importance === 'essential'
              ? 'bg-rose-100 text-rose-700 border border-rose-300'
              : 'bg-slate-100 text-slate-500 border border-slate-200'
          }`,
        },
        badgeText,
      ],
      ...(HTMLAttributes.sensitive
        ? [
            [
              'span',
              {
                class:
                  'text-[9px] px-1.5 py-0.2 rounded-full font-bold uppercase tracking-wider ml-0.5 bg-amber-100 text-amber-800 border border-amber-300',
              },
              '🔒 Sensitive',
            ],
          ]
        : []),
    ];
  },
});


export const PageBreak = Node.create({
  name: 'pageBreak',
  group: 'block',
  atom: true,
  draggable: true,

  parseHTML() {
    return [{ tag: 'div[data-type="page-break"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'div',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'page-break',
        class:
          'page-break my-6 py-2 border-b-2 border-dashed border-gray-400 text-center text-xs font-mono text-gray-500 uppercase tracking-widest bg-gray-50 rounded select-none',
      }),
      '--- PAGE BREAK ---',
    ];
  },
});

export function safeInsertBlock(editor: any, nodeJSON: any, position?: number) {
  if (!editor) return false;

  // A drop supplies an explicit document position.  Try that position first
  // so a palette block is inserted where the pointer was released rather than
  // wherever the editor happened to retain focus.
  if (typeof position === 'number' && Number.isFinite(position)) {
    try {
      if (editor.can().insertContentAt(position, nodeJSON)) {
        editor.chain().focus().insertContentAt(position, nodeJSON).run();
        return true;
      }
    } catch {
      // A position inside a table cell (or another inline-only context) may
      // reject a block.  Fall through to the context-aware block insertion.
    }
  }

  // insertContent replaces a non-empty selection. Inserting a block must never
  // delete existing content (e.g. when the whole document is selected), so only
  // insert at the cursor when the selection is collapsed; otherwise insert after it.
  if (editor.state.selection.empty) {
    try {
      if (editor.can().insertContent(nodeJSON)) {
        editor.chain().focus().insertContent(nodeJSON).run();
        return true;
      }
    } catch {
      // continue to fallback
    }
  }

  try {
    const { $to } = editor.state.selection;
    const depth = Math.min($to.depth, 1);
    const afterPos = depth > 0 ? $to.after(depth) : editor.state.doc.content.size;
    editor.chain().focus().insertContentAt(afterPos, nodeJSON).run();
    return true;
  } catch {
    try {
      editor.chain().focus().insertContentAt(editor.state.doc.content.size, nodeJSON).run();
      return true;
    } catch (err) {
      console.error('Failed to insert block:', err);
    }
  }
  return false;
}

export function insertInfoTable(editor: any, rows?: any[], position?: number) {
  const node = createInfoTableNode(rows);
  safeInsertBlock(editor, node, position);
}

export function insertRepeatingTable(editor: any, cols?: any[], listVar?: string, itemAlias?: string, position?: number) {
  const node = createRepeatingTableNode(cols, listVar, itemAlias);
  safeInsertBlock(editor, node, position);
}

export function insertSignatureGrid(editor: any, count = 2, signatures?: any[], position?: number) {
  const node = createSignatureGridNode(count, signatures);
  safeInsertBlock(editor, node, position);
}

export function insertImageBlock(editor: any, attributes: Partial<ImageBlockAttributes> = {}, position?: number) {
  const node = createImageBlockNode(attributes);
  safeInsertBlock(editor, node, position);
}

export function insertFieldChip(
  editor: any,
  fieldName: string,
  label?: string,
  fieldType = 'text',
  ask = '',
  importance = 'optional',
  required = false,
  sensitive = false,
  position?: number
) {
  const content = {
    type: 'fieldChip',
    attrs: {
      fieldName,
      label: label || fieldName,
      fieldType,
      ask: ask || `Please provide ${label || fieldName}`,
      importance,
      required: importance === 'essential' || required,
      sensitive,
    },
  };
  if (typeof position === 'number' && Number.isFinite(position)) {
    try {
      if (editor.can().insertContentAt(position, content)) {
        editor.chain().focus().insertContentAt(position, content).run();
        return;
      }
    } catch {
      // Use the current selection below when the requested position is no
      // longer valid after another editor transaction.
    }
  }
  // Never replace selected text with a chip; drop it at the end of the selection.
  const { selection } = editor.state;
  const chain = editor.chain().focus();
  (selection.empty ? chain : chain.setTextSelection(selection.to)).insertContent(content).run();
}

/**
 * Transparently converts legacy atom nodes (infoTable, repeatingTable, signatureGrid)
 * into native TipTap table nodes before loading into the editor.
 */
export function migrateTipTapContent(content: any): any {
  if (!content || !content.content || !Array.isArray(content.content)) {
    return content;
  }
  const migrateNode = (node: any): any => {
    if (!node || typeof node !== 'object') return node;
    let migrated = node;
    // Older integrations used the built-in image node or a small `logo` atom.
    // Normalize both to the editor's stable imageBlock schema before TipTap
    // attempts to parse the document.
    if (node.type === 'image' || node.type === 'logo' || node.type === 'clubLogo') {
      const attrs = node.attrs || {};
      const imageType = node.type === 'image' ? 'image' : 'club-logo';
      migrated = createImageBlockNode({
        imageType,
        src: attrs.src || attrs.url || attrs.logoUrl || '',
        alt: attrs.alt || (imageType === 'club-logo' ? 'Club logo' : 'Template image'),
        caption: attrs.title || attrs.caption || '',
        clubLogoAssetId: attrs.clubLogoAssetId || attrs.clubLogoId || attrs.logoAssetId || attrs.assetId || null,
        logoAssetId: attrs.logoAssetId || attrs.logoId || attrs.assetId || null,
        assetId: attrs.assetId || null,
        placement: attrs.placement || attrs.align || 'center',
        width: attrs.width || 'auto',
        height: attrs.height || 180,
        fit: attrs.fit || 'contain',
      });
    }
    if (migrated.content && Array.isArray(migrated.content)) {
      migrated = { ...migrated, content: migrated.content.map(migrateNode) };
    }
    return migrated;
  };

  const newContent: any[] = [];
  // Converted tables keep their blockId (and condition) so the AI copilot's references stay valid
  const keep = (node: any, from: any) => ({
    ...node,
    attrs: {
      ...(node.attrs || {}),
      ...(from.attrs?.blockId ? { blockId: from.attrs.blockId } : {}),
      ...(from.attrs?.showIf ? { showIf: from.attrs.showIf } : {}),
    },
  });
  for (const rawBlock of content.content) {
    const block = migrateNode(rawBlock);
    if (block.type === 'infoTable') {
      const rows = block.attrs?.rows || [];
      newContent.push(keep(createInfoTableNode(rows), block));
    } else if (block.type === 'repeatingTable') {
      const cols = block.attrs?.columns || [];
      const listVar = block.attrs?.listVariable || 'budget_items';
      const itemAlias = block.attrs?.itemAlias || 'item';
      const hasTotal = block.attrs?.hasTotal ?? true;
      const totalLabel = block.attrs?.totalLabel || 'Total';
      const totalVar = block.attrs?.totalVarName || `total_${listVar}_amount`;
      newContent.push(keep(createRepeatingTableNode(cols, listVar, itemAlias, hasTotal, totalLabel, totalVar), block));
    } else if (block.type === 'signatureGrid') {
      const signs = block.attrs?.signatures || [];
      const count = block.attrs?.columns || (signs.length > 0 ? signs.length : 2);
      newContent.push(keep(createSignatureGridNode(count, signs), block));
    } else {
      newContent.push(block);
    }
  }
  return ensureBlockIds({ ...content, content: newContent });
}
