import type { Editor } from '@tiptap/core';

export const FONT_SIZES = ['9', '10', '11', '12', '13', '14', '16', '18', '20', '24', '28', '32', '40'];

/** Set style attributes (fontFamily, fontSize, textColor, …) on the paragraphs and headings in the selection. */
export function applyBlockStyle(editor: Editor, attrs: Record<string, string | null>) {
  editor.chain().focus().updateAttributes('paragraph', attrs).updateAttributes('heading', attrs).run();
}

/** The style attributes of the text block holding the cursor. */
export function currentBlockStyle(editor: Editor): { fontFamily: string; fontSize: string } {
  const { $from } = editor.state.selection;
  for (let d = $from.depth; d > 0; d--) {
    const node = $from.node(d);
    if (node.isTextblock) {
      return { fontFamily: node.attrs.fontFamily || '', fontSize: String(node.attrs.fontSize || '').replace(/pt$/, '') };
    }
  }
  return { fontFamily: '', fontSize: '' };
}
