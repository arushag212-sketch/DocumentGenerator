import { Node, Extension, mergeAttributes } from '@tiptap/core';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';

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

export const CustomTable = Table.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      blockType: {
        default: 'generic',
        parseHTML: (element: any) => element.getAttribute('data-block-type') || 'generic',
        renderHTML: (attributes: any) => {
          const bt = attributes.blockType || 'generic';
          const classMap: Record<string, string> = {
            infoTable: 'cd-info-table',
            repeatingTable: 'cd-repeating-table',
            signatureGrid: 'cd-signature-grid',
          };
          const extra = classMap[bt] ? ` ${classMap[bt]}` : '';
          return {
            'data-block-type': bt,
            class: `cd-table cd-${bt}${extra}`,
          };
        },
      },
      listVariable: {
        default: null,
        parseHTML: (element: any) => element.getAttribute('data-list-var'),
        renderHTML: (attributes: any) => (attributes.listVariable ? { 'data-list-var': attributes.listVariable } : {}),
      },
      itemAlias: {
        default: null,
        parseHTML: (element: any) => element.getAttribute('data-item-alias'),
        renderHTML: (attributes: any) => (attributes.itemAlias ? { 'data-item-alias': attributes.itemAlias } : {}),
      },
      hasTotal: {
        default: false,
        parseHTML: (element: any) => element.getAttribute('data-has-total') === 'true',
        renderHTML: (attributes: any) => (attributes.hasTotal ? { 'data-has-total': 'true' } : {}),
      },
      totalLabel: {
        default: 'Total',
        parseHTML: (element: any) => element.getAttribute('data-total-label') || 'Total',
        renderHTML: (attributes: any) => (attributes.totalLabel ? { 'data-total-label': attributes.totalLabel } : {}),
      },
      totalVarName: {
        default: null,
        parseHTML: (element: any) => element.getAttribute('data-total-var'),
        renderHTML: (attributes: any) => (attributes.totalVarName ? { 'data-total-var': attributes.totalVarName } : {}),
      },
    };
  },

  renderHTML({ node, HTMLAttributes }): any {
    const bt = node.attrs.blockType || 'generic';
    const classMap: Record<string, string> = {
      infoTable: 'cd-info-table',
      repeatingTable: 'cd-repeating-table',
      signatureGrid: 'cd-signature-grid',
    };
    const extra = classMap[bt] ? ` ${classMap[bt]}` : '';
    const tableClass = `cd-table cd-${bt}${extra}`;

    const parentRender = this.parent?.({ node, HTMLAttributes }) as any;
    if (Array.isArray(parentRender) && parentRender.length >= 2) {
      parentRender[1] = mergeAttributes(parentRender[1] || {}, {
        class: tableClass,
        'data-block-type': bt,
      });
      return parentRender;
    }
    return ['table', mergeAttributes(HTMLAttributes, { class: tableClass, 'data-block-type': bt }), 0];
  },
});

export const CustomTableRow = TableRow;
export const CustomTableCell = TableCell;
export const CustomTableHeader = TableHeader;

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

// Helper Content Creators for Native Tables
export function createInfoTableNode(
  rows: Array<{ label: string; field?: string; value?: string }> = [
    { label: 'Event Title', field: 'event_name' },
    { label: 'Date', field: 'event_date' },
    { label: 'Venue', field: 'venue' },
  ]
) {
  return {
    type: 'table',
    attrs: { blockType: 'infoTable', class: 'cd-info-table' },
    content: rows.map(r => ({
      type: 'tableRow',
      content: [
        {
          type: 'tableCell',
          content: [{ type: 'paragraph', content: [{ type: 'text', text: r.label }] }],
        },
        {
          type: 'tableCell',
          content: [
            {
              type: 'paragraph',
              content: r.field
                ? [{ type: 'fieldChip', attrs: { fieldName: r.field, label: r.field, fieldType: 'text' } }]
                : r.value
                ? [{ type: 'text', text: r.value }]
                : [],
            },
          ],
        },
      ],
    })),
  };
}

export function createRepeatingTableNode(
  cols: Array<{ key: string; label: string }> = [
    { key: 'description', label: 'Item Description' },
    { key: 'amount', label: 'Amount (INR)' },
  ],
  listVar = 'budget_items',
  itemAlias = 'item',
  hasTotal = true,
  totalLabel = 'Total Budget',
  totalVarName = 'total_budget_amount'
) {
  const headerRow = {
    type: 'tableRow',
    content: cols.map(c => ({
      type: 'tableHeader',
      content: [{ type: 'paragraph', content: [{ type: 'text', text: c.label }] }],
    })),
  };

  const dataRow = {
    type: 'tableRow',
    content: cols.map(c => ({
      type: 'tableCell',
      content: [
        {
          type: 'paragraph',
          content: [
            {
              type: 'fieldChip',
              attrs: { fieldName: `${listVar}.${c.key}`, label: `${itemAlias}.${c.key}`, fieldType: 'text' },
            },
          ],
        },
      ],
    })),
  };

  const rows = [headerRow, dataRow];

  if (hasTotal && cols.length > 0) {
    const totalCells: any[] = [
      {
        type: 'tableCell',
        content: [{ type: 'paragraph', content: [{ type: 'text', text: totalLabel }] }],
      },
    ];
    for (let i = 0; i < cols.length - 2; i++) {
      totalCells.push({
        type: 'tableCell',
        content: [{ type: 'paragraph' }],
      });
    }
    if (cols.length > 1) {
      totalCells.push({
        type: 'tableCell',
        content: [
          {
            type: 'paragraph',
            content: [
              {
                type: 'fieldChip',
                attrs: { fieldName: totalVarName, label: totalVarName, fieldType: 'money' },
              },
            ],
          },
        ],
      });
    }
    rows.push({ type: 'tableRow', content: totalCells });
  }

  return {
    type: 'table',
    attrs: {
      blockType: 'repeatingTable',
      class: 'cd-repeating-table',
      listVariable: listVar,
      itemAlias: itemAlias,
      hasTotal: hasTotal,
      totalLabel: totalLabel,
      totalVarName: totalVarName,
    },
    content: rows,
  };
}

export function createSignatureGridNode(
  count = 2,
  signatures: Array<{ label: string; designation?: string }> = [
    { label: 'Student Chairperson', designation: 'Club Executive Committee' },
    { label: 'Faculty Advisor', designation: 'SVNIT Surat' },
  ]
) {
  const signs = signatures.slice(0, count);
  return {
    type: 'table',
    attrs: { blockType: 'signatureGrid', class: 'cd-signature-grid', columns: count },
    content: [
      {
        type: 'tableRow',
        content: signs.map(s => ({
          type: 'tableCell',
          content: [
            { type: 'paragraph', content: [{ type: 'text', text: s.label }] },
            { type: 'paragraph', content: [{ type: 'text', text: s.designation || '' }] },
          ],
        })),
      },
    ],
  };
}

export function safeInsertBlock(editor: any, nodeJSON: any) {
  if (!editor) return;
  try {
    if (editor.can().insertContent(nodeJSON)) {
      editor.chain().focus().insertContent(nodeJSON).run();
      return;
    }
  } catch {
    // continue to fallback
  }

  try {
    const { $to } = editor.state.selection;
    const depth = Math.min($to.depth, 1);
    const afterPos = depth > 0 ? $to.after(depth) : editor.state.doc.content.size;
    editor.chain().focus().insertContentAt(afterPos, nodeJSON).run();
  } catch {
    try {
      editor.chain().focus().insertContentAt(editor.state.doc.content.size, nodeJSON).run();
    } catch (err) {
      console.error('Failed to insert block:', err);
    }
  }
}

export function insertInfoTable(editor: any, rows?: any[]) {
  const node = createInfoTableNode(rows);
  safeInsertBlock(editor, node);
}

export function insertRepeatingTable(editor: any, cols?: any[], listVar?: string, itemAlias?: string) {
  const node = createRepeatingTableNode(cols, listVar, itemAlias);
  safeInsertBlock(editor, node);
}

export function insertSignatureGrid(editor: any, count = 2, signatures?: any[]) {
  const node = createSignatureGridNode(count, signatures);
  safeInsertBlock(editor, node);
}

export function insertFieldChip(
  editor: any,
  fieldName: string,
  label?: string,
  fieldType = 'text',
  ask = '',
  importance = 'optional',
  required = false,
  sensitive = false
) {
  editor
    .chain()
    .focus()
    .insertContent({
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
    })
    .run();
}

/**
 * Transparently converts legacy atom nodes (infoTable, repeatingTable, signatureGrid)
 * into native TipTap table nodes before loading into the editor.
 */
export function migrateTipTapContent(content: any): any {
  if (!content || !content.content || !Array.isArray(content.content)) {
    return content;
  }
  const newContent: any[] = [];
  for (const block of content.content) {
    if (block.type === 'infoTable') {
      const rows = block.attrs?.rows || [];
      newContent.push(createInfoTableNode(rows));
    } else if (block.type === 'repeatingTable') {
      const cols = block.attrs?.columns || [];
      const listVar = block.attrs?.listVariable || 'budget_items';
      const itemAlias = block.attrs?.itemAlias || 'item';
      const hasTotal = block.attrs?.hasTotal ?? true;
      const totalLabel = block.attrs?.totalLabel || 'Total';
      const totalVar = block.attrs?.totalVarName || `total_${listVar}_amount`;
      newContent.push(createRepeatingTableNode(cols, listVar, itemAlias, hasTotal, totalLabel, totalVar));
    } else if (block.type === 'signatureGrid') {
      const signs = block.attrs?.signatures || [];
      const count = block.attrs?.columns || (signs.length > 0 ? signs.length : 2);
      newContent.push(createSignatureGridNode(count, signs));
    } else {
      newContent.push(block);
    }
  }
  return { ...content, content: newContent };
}
