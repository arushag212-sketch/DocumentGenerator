import { Node, Extension, mergeAttributes } from '@tiptap/core';

export const AiSuggestedBlock = Extension.create({
  name: 'aiSuggestedBlock',
  addGlobalAttributes() {
    return [
      {
        types: ['heading', 'paragraph'],
        attributes: {
          ai_suggested: {
            default: false,
            parseHTML: element => element.getAttribute('data-ai-suggested') === 'true',
            renderHTML: attributes => {
              if (!attributes.ai_suggested) return {};
              return { 'data-ai-suggested': 'true' };
            },
          },
          official_wording_required: {
            default: false,
            parseHTML: element => element.getAttribute('data-official-wording') === 'true',
            renderHTML: attributes => {
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

  addAttributes() {
    return {
      fieldName: { default: '' },
      label: { default: '' },
      fieldType: { default: 'text' },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-field-name]',
        getAttrs: (element) => {
          const el = element as HTMLElement;
          return {
            fieldName: el.getAttribute('data-field-name'),
            label: el.getAttribute('data-label'),
            fieldType: el.getAttribute('data-field-type'),
          };
        },
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    const fieldName = HTMLAttributes.fieldName || '';
    const label = HTMLAttributes.label || fieldName;
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-field-name': fieldName,
        'data-label': label,
        'data-field-type': HTMLAttributes.fieldType || 'text',
        class:
          'field-chip inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 border border-indigo-300 shadow-sm mx-1 cursor-pointer select-none',
      }),
      `⚡ ${label}`,
    ];
  },
});

export const InfoTable = Node.create({
  name: 'infoTable',
  group: 'block',
  atom: true,

  addAttributes() {
    return {
      title: { default: 'Details' },
      ai_suggested: {
        default: false,
        parseHTML: element => element.getAttribute('data-ai-suggested') === 'true',
        renderHTML: attributes => (attributes.ai_suggested ? { 'data-ai-suggested': 'true' } : {}),
      },
      rows: {
        default: [
          { label: 'Event Title', field: 'event_name', value: '' },
          { label: 'Date', field: 'event_date', value: '' },
          { label: 'Venue', field: 'venue', value: '' },
        ],
      },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-type="info-table"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    const rows = HTMLAttributes.rows || [];
    const isAi = HTMLAttributes.ai_suggested || HTMLAttributes['data-ai-suggested'] === 'true';
    const rowElements = rows.map((r: any) => [
      'tr',
      { class: 'border-b border-slate-200' },
      ['td', { class: 'py-2 px-3 bg-slate-100 font-semibold text-xs text-slate-700 w-1/3' }, r.label || 'Label'],
      [
        'td',
        { class: 'py-2 px-3 text-xs text-slate-800 bg-white' },
        r.field
          ? [
              'span',
              {
                class:
                  'field-chip inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 border border-indigo-300 shadow-xs',
              },
              `⚡ ${r.field}`,
            ]
          : r.value || '',
      ],
    ]);

    return [
      'div',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'info-table',
        class: 'info-table-block my-4 p-3 border border-slate-300 rounded-lg bg-slate-50 shadow-sm',
      }),
      ['div', { class: 'text-xs font-bold text-slate-600 uppercase tracking-wide mb-2 flex items-center justify-between' },
        ['span', { class: 'flex items-center gap-2' },
          ['span', {}, '📋 Info Table (Label : Value)'],
          isAi ? ['span', { class: 'text-[9px] bg-purple-100 text-purple-700 font-semibold px-2 py-0.5 rounded-full border border-purple-200 shadow-xs' }, 'AI-suggested'] : '',
        ],
        ['span', { class: 'text-[10px] text-slate-400 font-normal' }, `${rows.length} rows`],
      ],
      ['table', { class: 'w-full text-left border-collapse border border-slate-200 rounded overflow-hidden' },
        ['tbody', {}, ...rowElements],
      ],
    ];
  },
});

export const RepeatingTable = Node.create({
  name: 'repeatingTable',
  group: 'block',
  atom: true,

  addAttributes() {
    return {
      listVariable: { default: 'sponsorship_tiers' },
      itemAlias: { default: 'tier' },
      ai_suggested: {
        default: false,
        parseHTML: element => element.getAttribute('data-ai-suggested') === 'true',
        renderHTML: attributes => (attributes.ai_suggested ? { 'data-ai-suggested': 'true' } : {}),
      },
      columns: {
        default: [
          { key: 'tier_name', label: 'Tier', align: 'left' },
          { key: 'benefits', label: 'Benefits', align: 'left' },
          { key: 'amount', label: 'Contribution (INR)', align: 'right' },
        ],
      },
      hasTotal: { default: true },
      totalLabel: { default: 'Total Contribution' },
      totalField: { default: 'amount' },
      totalVarName: { default: 'total_sponsorship_amount' },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-type="repeating-table"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    const cols = HTMLAttributes.columns || [];
    const listVar = HTMLAttributes.listVariable || 'items';
    const isAi = HTMLAttributes.ai_suggested || HTMLAttributes['data-ai-suggested'] === 'true';

    const headerCols = cols.map((c: any) => [
      'th',
      { class: `py-2 px-3 bg-blue-100 text-blue-900 font-bold text-xs uppercase tracking-wider text-${c.align || 'left'}` },
      c.label || c.key,
    ]);

    const sampleRow = cols.map((c: any) => [
      'td',
      { class: `py-2 px-3 text-xs text-slate-700 bg-white text-${c.align || 'left'}` },
      [
        'span',
        {
          class:
            'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200',
        },
        `⚡ ${c.key}`,
      ],
    ]);

    const rows = [
      ['tr', {}, ...headerCols],
      ['tr', { class: 'border-b border-blue-100' }, ...sampleRow],
    ];

    if (HTMLAttributes.hasTotal) {
      rows.push([
        'tr',
        { class: 'bg-blue-50/80 font-bold border-t-2 border-blue-300' },
        ['td', { class: 'py-2 px-3 text-xs text-blue-950 font-bold' }, HTMLAttributes.totalLabel || 'Total'],
        ...Array(Math.max(cols.length - 2, 0)).fill(['td', { class: 'py-2 px-3' }, '']),
        [
          'td',
          { class: 'py-2 px-3 text-xs text-blue-950 font-bold text-right' },
          [
            'span',
            {
              class:
                'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-200 text-blue-900 border border-blue-300',
            },
            `⚡ ∑ ${HTMLAttributes.totalVarName || 'total_amount'}`,
          ],
        ],
      ]);
    }

    return [
      'div',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'repeating-table',
        class: 'repeating-table-block my-4 p-3 border border-blue-200 rounded-lg bg-blue-50/40 shadow-sm',
      }),
      ['div', { class: 'text-xs font-bold text-blue-800 uppercase tracking-wide mb-2 flex items-center justify-between' },
        ['span', { class: 'flex items-center gap-2' },
          ['span', { class: 'font-bold' }, '🔁 Repeating Table'],
          ['span', { class: 'text-[11px] font-normal px-2 py-0.5 rounded bg-blue-200 text-blue-800' }, `repeats for each row of <${listVar}>`],
          isAi ? ['span', { class: 'text-[9px] bg-purple-100 text-purple-700 font-semibold px-2 py-0.5 rounded-full border border-purple-200 shadow-xs' }, 'AI-suggested'] : '',
        ],
        ['span', { class: 'text-[10px] text-blue-600 bg-blue-100 px-2 py-0.5 rounded' }, HTMLAttributes.hasTotal ? 'Computed Total Enabled' : 'No Total'],
      ],
      ['table', { class: 'w-full text-left border-collapse border border-blue-200 rounded overflow-hidden' },
        ['tbody', {}, ...rows],
      ],
    ];
  },
});

export const SignatureGrid = Node.create({
  name: 'signatureGrid',
  group: 'block',
  atom: true,

  addAttributes() {
    return {
      columns: { default: 3 },
      ai_suggested: {
        default: false,
        parseHTML: element => element.getAttribute('data-ai-suggested') === 'true',
        renderHTML: attributes => (attributes.ai_suggested ? { 'data-ai-suggested': 'true' } : {}),
      },
      signatures: {
        default: [
          { label: 'Student Coordinator', designation: 'ACM Student Chapter' },
          { label: 'Faculty Advisor', designation: 'DoCSE, SVNIT' },
          { label: 'Head of Department', designation: 'DoCSE, SVNIT' },
        ],
      },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-type="signature-grid"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    const signs = HTMLAttributes.signatures || [];
    const isAi = HTMLAttributes.ai_suggested || HTMLAttributes['data-ai-suggested'] === 'true';
    const cols = signs.map((s: any) => [
      'div',
      { class: 'flex-1 text-center p-3 border border-gray-200 bg-white rounded flex flex-col items-center justify-between min-h-[90px]' },
      ['div', { class: 'w-full border-b border-gray-300 mt-6 mb-2' }],
      ['div', { class: 'text-xs font-bold text-gray-800' }, s.label || 'Signee'],
      ['div', { class: 'text-[10px] text-gray-500' }, s.designation || ''],
    ]);

    return [
      'div',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'signature-grid',
        class: 'signature-grid-block my-6 p-4 border border-gray-300 rounded-lg bg-gray-50 shadow-sm',
      }),
      ['div', { class: 'text-xs font-bold text-gray-600 uppercase tracking-wide mb-3 flex items-center justify-between' },
        ['span', { class: 'flex items-center gap-2' },
          ['span', {}, '✍️ Signature Grid (Keeps Rows Together)'],
          isAi ? ['span', { class: 'text-[9px] bg-purple-100 text-purple-700 font-semibold px-2 py-0.5 rounded-full border border-purple-200 shadow-xs' }, 'AI-suggested'] : '',
        ],
        ['span', { class: 'text-[10px] text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded font-mono' }, 'cantSplit & keepWithNext'],
      ],
      ['div', { class: 'flex gap-4' }, ...cols],
    ];
  },
});

export const PageBreak = Node.create({
  name: 'pageBreak',
  group: 'block',
  atom: true,

  parseHTML() {
    return [{ tag: 'div[data-type="page-break"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'div',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'page-break',
        class: 'page-break my-6 py-2 border-b-2 border-dashed border-gray-400 text-center text-xs font-mono text-gray-500 uppercase tracking-widest bg-gray-50 rounded select-none',
      }),
      '--- PAGE BREAK ---',
    ];
  },
});
