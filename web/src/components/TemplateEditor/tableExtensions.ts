import { mergeAttributes } from '@tiptap/core';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';

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
