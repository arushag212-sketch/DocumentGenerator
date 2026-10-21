import { useState } from 'react';
import { useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import TextAlign from '@tiptap/extension-text-align';
import Underline from '@tiptap/extension-underline';
import { NodeSelection } from '@tiptap/pm/state';
import {
  CustomTable,
  CustomTableRow,
  CustomTableCell,
  CustomTableHeader,
  AiSuggestedBlock,
  FieldChip,
  ImageBlock,
  PageBreak,
  BlockIdExtension,
} from './extensions';
import { handleEditorDrop, moveTopLevelBlock } from './blockDragDrop';

export interface InlinePickerState {
  type: 'slash' | 'field';
  top: number;
  left: number;
  range: { from: number; to: number };
}

interface UseTemplateEditorOptions {
  onDocChange?: () => void;
  clubId?: string;
}

/** Position of the field chip at (or right next to) `pos`, preferring the one with `fieldName`. */
function findChipPos(doc: any, pos: number, fieldName?: string): number | null {
  for (const p of [pos, pos - 1, pos + 1]) {
    if (p < 0 || p > doc.content.size) continue;
    const n = doc.nodeAt(p);
    if (n && n.type.name === 'fieldChip' && (!fieldName || n.attrs.fieldName === fieldName)) return p;
  }
  return null;
}

export function useTemplateEditor({ onDocChange, clubId }: UseTemplateEditorOptions = {}) {
  const [bubblePos, setBubblePos] = useState<{ top: number; left: number } | null>(null);
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [inlinePicker, setInlinePicker] = useState<InlinePickerState | null>(null);
  const [chipPopover, setChipPopover] = useState<any>(null);
  const [selectedImageBlock, setSelectedImageBlock] = useState<any>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      Underline,
      CustomTable.configure({
        resizable: true,
      }),
      CustomTableRow,
      CustomTableCell,
      CustomTableHeader,
      AiSuggestedBlock,
      FieldChip,
      ImageBlock,
      PageBreak,
      BlockIdExtension,
    ],
    editorProps: {
      handleDrop: (view, event) => {
        return handleEditorDrop(view, event, clubId);
      },
      handleClick: (view, pos, event) => {
        const target = event.target as HTMLElement;
        const imageTarget = target.closest('.image-block');
        if (imageTarget) {
          let targetPos = pos;
          try {
            const domPos = view.posAtDOM(imageTarget, 0);
            if (domPos !== null && domPos !== undefined) {
              targetPos = domPos;
            }
          } catch {
            // fallback
          }
          const imageNode = view.state.doc.nodeAt(targetPos) || view.state.doc.nodeAt(pos);
          if (imageNode && (imageNode.type.name === 'imageBlock' || imageNode.type.name === 'image')) {
            const validPos = view.state.doc.nodeAt(targetPos)?.type.name === imageNode.type.name ? targetPos : pos;
            try {
              view.dispatch(view.state.tr.setSelection(NodeSelection.create(view.state.doc, validPos)));
            } catch {
              // ignore
            }
            setSelectedImageBlock({ position: validPos, attrs: { ...imageNode.attrs } });
            setChipPopover(null);
            setBubblePos(null);
            return true;
          }
        }

        const fieldTarget = target.closest('.field-chip');
        if (fieldTarget) {
          const rect = fieldTarget.getBoundingClientRect();
          // The click position can be just after the chip; use the chip's own position
          const domName = fieldTarget.getAttribute('data-field-name') || '';
          pos = findChipPos(view.state.doc, pos, domName) ?? pos;
          const node = view.state.doc.nodeAt(pos);
          const attrs = node?.type.name === 'fieldChip' ? node.attrs : {};
          const fieldName = attrs.fieldName || fieldTarget.getAttribute('data-field-name') || '';
          const label = attrs.label || fieldTarget.getAttribute('data-label') || fieldName;
          const fieldType = attrs.fieldType || fieldTarget.getAttribute('data-field-type') || 'text';
          const importance = attrs.importance || 'optional';
          const required = importance === 'essential' || attrs.required;
          const sensitive = attrs.sensitive || false;

          view.dispatch(view.state.tr.setSelection(NodeSelection.create(view.state.doc, pos)));
          setChipPopover({
            top: Math.min(rect.bottom + 8, window.innerHeight - 300),
            left: Math.min(Math.max(rect.left, 20), window.innerWidth - 320),
            position: pos,
            fieldName,
            label,
            fieldType,
            importance,
            required,
            sensitive,
          });
          setSelectedImageBlock(null);
          return true;
        } else {
          setChipPopover(null);
          setSelectedImageBlock(null);
        }
        return false;
      },
      handleKeyDown: (view, event): boolean => {
        if (event.key === 'Escape') {
          setChipPopover(null);
          setSelectedImageBlock(null);
          setShowSlashMenu(false);
          setInlinePicker(null);
          return true;
        }
        if (event.altKey && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
          event.preventDefault();
          const direction = event.key === 'ArrowUp' ? 'up' : 'down';
          return moveTopLevelBlock(view, direction);
        }
        return false;
      },
    },
    content: { type: 'doc', content: [] },
    onSelectionUpdate: ({ editor: currentEditor }) => {
      const { selection } = currentEditor.state;
      if (!selection || selection.empty) {
        setBubblePos(null);
        return;
      }
      try {
        const coords = currentEditor.view.coordsAtPos(selection.from);
        setBubblePos({
          top: Math.max(coords.top - 44, 10),
          left: Math.min(Math.max(coords.left, 20), Math.max(20, window.innerWidth - 240)),
        });
      } catch {
        setBubblePos(null);
      }
    },
    onBlur: ({ event }: any) => {
      const next = event?.relatedTarget as HTMLElement | null;
      if (next && next.closest('[data-editor-bubble]')) return;
      setBubblePos(null);
    },
    onUpdate: ({ editor: currentEditor, transaction }: any) => {
      if (onDocChange) onDocChange();

      // Check for inline trigger: '{{' or '/'
      const { selection } = currentEditor.state;
      const { $from } = selection;
      const textBefore = $from.parent.textBetween(0, $from.parentOffset, undefined, '\ufffc');

      if (textBefore.endsWith('{{')) {
        try {
          const coords = currentEditor.view.coordsAtPos(selection.from);
          setInlinePicker({
            type: 'field',
            top: coords.bottom + 6,
            left: Math.min(Math.max(coords.left, 20), Math.max(20, window.innerWidth - 300)),
            range: { from: selection.from - 2, to: selection.from },
          });
          setShowSlashMenu(false);
        } catch {
          setInlinePicker(null);
        }
      } else if (textBefore === '/' || textBefore.endsWith(' /')) {
        try {
          const coords = currentEditor.view.coordsAtPos(selection.from);
          const slashStart = textBefore.endsWith(' /') ? selection.from - 1 : selection.from - 1;
          setInlinePicker({
            type: 'slash',
            top: coords.bottom + 6,
            left: Math.min(Math.max(coords.left, 20), Math.max(20, window.innerWidth - 300)),
            range: { from: slashStart, to: selection.from },
          });
          setShowSlashMenu(true);
        } catch {
          setShowSlashMenu(true);
        }
      } else if (inlinePicker && !textBefore.includes('{{') && !textBefore.includes('/')) {
        setInlinePicker(null);
        setShowSlashMenu(false);
      }

      // Clear AI flag on edited paragraph
      if (transaction && transaction.docChanged) {
        const { from } = currentEditor.state.selection;
        const resolved = currentEditor.state.doc.resolve(from);
        for (let d = resolved.depth; d > 0; d--) {
          const node = resolved.node(d);
          if (node.attrs && (node.attrs.ai_suggested || node.attrs.official_wording_required)) {
            const nodePos = resolved.before(d);
            currentEditor.commands.command(({ tr }: any) => {
              tr.setNodeMarkup(nodePos, undefined, {
                ...node.attrs,
                ai_suggested: false,
                official_wording_required: false,
              });
              return true;
            });
            break;
          }
        }
      }
    },
  });

  // Change some of a field chip's attributes. setNodeMarkup replaces *all* attributes, so the
  // chip's current ones are merged in; the popover state follows so its inputs stay in sync.
  const patchChip = (updates: Record<string, any>) => {
    if (!chipPopover || !editor) return;
    const pos = findChipPos(editor.state.doc, chipPopover.position, chipPopover.fieldName);
    if (pos === null) return;
    const node = editor.state.doc.nodeAt(pos)!;
    editor.view.dispatch(editor.state.tr.setNodeMarkup(pos, undefined, { ...node.attrs, ...updates }));
    setChipPopover((prev: any) => (prev ? { ...prev, ...updates } : prev));
    if (onDocChange) onDocChange();
  };

  const updateChip = (updates: any) => patchChip(updates);

  const toggleChipRequired = (req: boolean) => patchChip({ importance: req ? 'essential' : 'optional', required: req });

  const toggleChipSensitive = (sens: boolean) => patchChip({ sensitive: sens });

  const deleteChip = () => {
    if (!chipPopover || !editor) return;
    editor.chain().focus().setNodeSelection(chipPopover.position).deleteSelection().run();
    setChipPopover(null);
    if (onDocChange) onDocChange();
  };

  const updateImageBlock = (updates: any) => {
    if (!selectedImageBlock || !editor) return;
    editor.chain().focus().setNodeSelection(selectedImageBlock.position).updateAttributes('imageBlock', updates).run();
    if (onDocChange) onDocChange();
  };

  return {
    editor,
    bubblePos,
    setBubblePos,
    showSlashMenu,
    setShowSlashMenu,
    inlinePicker,
    setInlinePicker,
    chipPopover,
    setChipPopover,
    selectedImageBlock,
    setSelectedImageBlock,
    updateChip,
    toggleChipRequired,
    toggleChipSensitive,
    deleteChip,
    updateImageBlock,
  };
}
