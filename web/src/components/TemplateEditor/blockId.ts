import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';

export function generateBlockId(prefix = 'b'): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;
  }
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}_${Date.now().toString(36)}`;
}

export const BLOCK_NODE_TYPES = ['paragraph', 'heading', 'table', 'imageBlock', 'pageBreak'];

/**
 * TipTap extension that guarantees a stable, unique blockId attribute
 * on every top-level and structural block node.
 */
export const BlockIdExtension = Extension.create({
  name: 'blockId',

  addGlobalAttributes() {
    return [
      {
        types: BLOCK_NODE_TYPES,
        attributes: {
          blockId: {
            default: null,
            rendered: true,
            keepOnSplit: false,
            parseHTML: (element: HTMLElement) => element.getAttribute('data-block-id') || null,
            renderHTML: (attributes: Record<string, any>) => {
              if (!attributes.blockId) return {};
              return { 'data-block-id': attributes.blockId };
            },
          },
        },
      },
    ];
  },

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('blockIdAutoAssign'),
        appendTransaction(transactions, _oldState, newState) {
          const docChanged = transactions.some((tr) => tr.docChanged);
          if (!docChanged) return null;

          const tr = newState.tr;
          let modified = false;

          newState.doc.forEach((node, offset) => {
            if (BLOCK_NODE_TYPES.includes(node.type.name) && !node.attrs.blockId) {
              tr.setNodeMarkup(offset, undefined, {
                ...node.attrs,
                blockId: generateBlockId(),
              });
              modified = true;
            }
          });

          return modified ? tr : null;
        },
      }),
    ];
  },
});

/**
 * Traverses an editor JSON object and ensures every block node has a blockId.
 * Used during initial JSON migration / loading before TipTap mounts.
 */
export function ensureBlockIds(content: any): any {
  if (!content || typeof content !== 'object') return content;

  if (Array.isArray(content)) {
    return content.map(ensureBlockIds);
  }

  const updated = { ...content };
  if (BLOCK_NODE_TYPES.includes(updated.type)) {
    const attrs = { ...(updated.attrs || {}) };
    if (!attrs.blockId) {
      attrs.blockId = generateBlockId();
    }
    updated.attrs = attrs;
  }

  if (Array.isArray(updated.content)) {
    updated.content = updated.content.map(ensureBlockIds);
  }

  return updated;
}
