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

interface UseTemplateEditorOptions {
  onDocChange?: () => void;
  clubId?: string;
}

export function useTemplateEditor({ onDocChange, clubId }: UseTemplateEditorOptions = {}) {
  const [bubblePos, setBubblePos] = useState<{ top: number; left: number } | null>(null);
  const [showSlashMenu, setShowSlashMenu] = useState(false);
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
          const imageNode = view.state.doc.nodeAt(pos);
          if (imageNode) {
            view.dispatch(view.state.tr.setSelection(NodeSelection.create(view.state.doc, pos)));
            setSelectedImageBlock({ position: pos, attrs: { ...imageNode.attrs } });
            setChipPopover(null);
            setBubblePos(null);
            return true;
          }
        }

        const fieldTarget = target.closest('.field-chip');
        if (fieldTarget) {
          const rect = fieldTarget.getBoundingClientRect();
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
    onBlur: () => {
      setBubblePos(null);
    },
    onUpdate: ({ editor: currentEditor, transaction }: any) => {
      if (onDocChange) onDocChange();

      // Check for slash command at the start of empty line
      const { selection } = currentEditor.state;
      const { $from } = selection;
      const textBefore = $from.parent.textBetween(0, $from.parentOffset, undefined, '\ufffc');
      if (textBefore === '/') {
        setShowSlashMenu(true);
      } else if (showSlashMenu) {
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

  const updateChip = (updates: any) => {
    if (!chipPopover || !editor) return;
    editor.commands.command(({ tr }: any) => {
      tr.setNodeMarkup(chipPopover.position, undefined, updates);
      return true;
    });
    if (onDocChange) onDocChange();
  };

  const toggleChipRequired = (req: boolean) => {
    if (!chipPopover || !editor) return;
    const imp = req ? 'essential' : 'optional';
    editor.commands.command(({ tr }: any) => {
      tr.setNodeMarkup(chipPopover.position, undefined, {
        importance: imp,
        required: req,
      });
      return true;
    });
    setChipPopover((prev: any) => ({ ...prev, required: req, importance: imp }));
    if (onDocChange) onDocChange();
  };

  const toggleChipSensitive = (sens: boolean) => {
    if (!chipPopover || !editor) return;
    editor.commands.command(({ tr }: any) => {
      tr.setNodeMarkup(chipPopover.position, undefined, { sensitive: sens });
      return true;
    });
    setChipPopover((prev: any) => ({ ...prev, sensitive: sens }));
    if (onDocChange) onDocChange();
  };

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
