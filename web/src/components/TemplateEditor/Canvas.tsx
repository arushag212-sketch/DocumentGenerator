import React, { useState, useEffect, useRef } from 'react';
import { EditorContent } from '@tiptap/react';
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  AlignLeft,
  AlignCenter,
  AlignRight,
  AlignJustify,
  Sparkles,
  Table as TableIcon,
  Rows,
  CheckSquare,
  SplitSquareVertical,
  Heading1,
  Heading2,
  Trash2,
  Lock,
} from 'lucide-react';
import { A4Page } from './A4Page';
import {
  insertInfoTable,
  insertRepeatingTable,
  insertSignatureGrid,
  insertImageBlock,
  insertFieldChip,
  safeInsertBlock,
} from './extensions';

interface CanvasProps {
  editor: any;
  zoom: number;
  watermarkText?: string;
  orientation?: 'portrait' | 'landscape';
  margins?: 'normal' | 'compact' | 'wide';
  bubblePos: { top: number; left: number } | null;
  chipPopover: any;
  onCloseChipPopover: () => void;
  onUpdateChip: (updates: any) => void;
  onToggleChipRequired: (req: boolean) => void;
  onToggleChipSensitive: (sens: boolean) => void;
  onDeleteChip: () => void;
  selectedImageBlock: any;
  onUpdateImageBlock: (updates: any) => void;
  clubLogoOptions?: any[];
  showSlashMenu: boolean;
  onCloseSlashMenu: () => void;
  onOpenAddField: () => void;
}

export const Canvas: React.FC<CanvasProps> = ({
  editor,
  zoom,
  watermarkText,
  orientation = 'portrait',
  margins = 'normal',
  bubblePos,
  chipPopover,
  onCloseChipPopover,
  onUpdateChip,
  onToggleChipRequired,
  onToggleChipSensitive,
  onDeleteChip,
  selectedImageBlock: _selectedImageBlock,
  onUpdateImageBlock: _onUpdateImageBlock,
  clubLogoOptions: _clubLogoOptions = [],
  showSlashMenu,
  onCloseSlashMenu,
  onOpenAddField,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [wordCount, setWordCount] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const [blockCount, setBlockCount] = useState(0);

  // Update statistics
  useEffect(() => {
    if (!editor) return;
    const updateStats = () => {
      const doc = editor.state.doc;
      const text = doc.textBetween(0, doc.content.size, ' ');
      const words = text.trim() ? text.trim().split(/\s+/).length : 0;
      setWordCount(words);
      setCharCount(text.length);
      setBlockCount(doc.childCount);
    };

    updateStats();
    editor.on('update', updateStats);
    return () => {
      editor.off('update', updateStats);
    };
  }, [editor]);

  // Slash commands list
  const slashItems = [
    {
      title: 'Heading 1',
      icon: <Heading1 className="w-4 h-4 text-indigo-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).setHeading({ level: 1 }).run();
        onCloseSlashMenu();
      },
    },
    {
      title: 'Heading 2',
      icon: <Heading2 className="w-4 h-4 text-indigo-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).setHeading({ level: 2 }).run();
        onCloseSlashMenu();
      },
    },
    {
      title: 'Info Table (Key-Value)',
      icon: <TableIcon className="w-4 h-4 text-emerald-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        insertInfoTable(editor);
        onCloseSlashMenu();
      },
    },
    {
      title: 'Repeating Table (Items & Sum)',
      icon: <Rows className="w-4 h-4 text-blue-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        insertRepeatingTable(editor);
        onCloseSlashMenu();
      },
    },
    {
      title: 'Signature Grid (Signatures)',
      icon: <CheckSquare className="w-4 h-4 text-amber-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        insertSignatureGrid(editor, 2);
        onCloseSlashMenu();
      },
    },
    {
      title: 'Insert Field Chip',
      icon: <Sparkles className="w-4 h-4 text-purple-600" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        onOpenAddField();
        onCloseSlashMenu();
      },
    },
    {
      title: 'Page Break',
      icon: <SplitSquareVertical className="w-4 h-4 text-rose-500" />,
      action: () => {
        editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).insertContent({ type: 'pageBreak' }).run();
        onCloseSlashMenu();
      },
    },
  ];

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (!editor) return;

    const blockData = e.dataTransfer.getData('application/x-clubdocs-block');
    const fieldData = e.dataTransfer.getData('application/x-clubdocs-field');

    if (fieldData) {
      try {
        const parsed = JSON.parse(fieldData);
        insertFieldChip(
          editor,
          parsed.fieldName,
          parsed.label,
          parsed.fieldType,
          parsed.ask,
          parsed.importance,
          parsed.required,
          parsed.sensitive
        );
      } catch (err) {
        console.error('Failed to drop field:', err);
      }
      return;
    }

    if (blockData) {
      try {
        const parsed = JSON.parse(blockData);
        if (parsed.type === 'heading1') editor.chain().focus().setHeading({ level: 1 }).run();
        else if (parsed.type === 'heading2') editor.chain().focus().setHeading({ level: 2 }).run();
        else if (parsed.type === 'heading3') editor.chain().focus().setHeading({ level: 3 }).run();
        else if (parsed.type === 'paragraph') editor.chain().focus().setParagraph().run();
        else if (parsed.type === 'infoTable') insertInfoTable(editor);
        else if (parsed.type === 'repeatingTable') insertRepeatingTable(editor);
        else if (parsed.type === 'signatureGrid') insertSignatureGrid(editor, 2);
        else if (parsed.type === 'clubLogo') insertImageBlock(editor, { imageType: 'club-logo', alt: 'Club logo' });
        else if (parsed.type === 'pageBreak') safeInsertBlock(editor, { type: 'pageBreak' });
      } catch (err) {
        console.error('Failed to drop block:', err);
      }
    }
  };

  return (
    <div
      ref={containerRef}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      className="relative flex-1 bg-slate-100 overflow-y-auto flex flex-col items-center select-text"
    >
      {/* Floating Selection Bubble Menu */}
      {bubblePos && editor && (
        <div
          style={{ top: `${bubblePos.top}px`, left: `${bubblePos.left}px` }}
          className="fixed z-40 flex items-center gap-0.5 bg-slate-900/95 backdrop-blur text-white px-1.5 py-1 rounded-lg shadow-xl border border-slate-700 animate-in fade-in zoom-in-95 duration-100"
        >
          <button
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive('bold') ? 'text-indigo-400 bg-slate-800' : 'text-slate-200'}`}
            title="Bold"
          >
            <Bold className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive('italic') ? 'text-indigo-400 bg-slate-800' : 'text-slate-200'}`}
            title="Italic"
          >
            <Italic className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive('underline') ? 'text-indigo-400 bg-slate-800' : 'text-slate-200'}`}
            title="Underline"
          >
            <UnderlineIcon className="w-3.5 h-3.5" />
          </button>

          <div className="w-px h-3.5 bg-slate-700 mx-0.5" />

          <button
            onClick={() => editor.chain().focus().setTextAlign('left').run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive({ textAlign: 'left' }) ? 'text-indigo-400 bg-slate-800' : 'text-slate-200'}`}
            title="Align Left"
          >
            <AlignLeft className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().setTextAlign('center').run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive({ textAlign: 'center' }) ? 'text-indigo-400 bg-slate-800' : 'text-slate-200'}`}
            title="Align Center"
          >
            <AlignCenter className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().setTextAlign('right').run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive({ textAlign: 'right' }) ? 'text-indigo-400 bg-slate-800' : 'text-slate-200'}`}
            title="Align Right"
          >
            <AlignRight className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().setTextAlign('justify').run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive({ textAlign: 'justify' }) ? 'text-indigo-400 bg-slate-800' : 'text-slate-200'}`}
            title="Justify"
          >
            <AlignJustify className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Slash Command Popover Menu */}
      {showSlashMenu && (
        <div className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-2xl w-64 p-1.5 animate-in fade-in zoom-in-95">
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-2 py-1">
            Insert Block
          </div>
          <div className="space-y-0.5">
            {slashItems.map((item, idx) => (
              <button
                key={idx}
                onClick={item.action}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-xs text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 transition"
              >
                {item.icon}
                <span className="font-medium">{item.title}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Field Chip Edit Popover */}
      {chipPopover && (
        <div
          style={{ top: `${chipPopover.top}px`, left: `${chipPopover.left}px` }}
          className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-2xl p-3.5 w-72 text-xs space-y-3 animate-in fade-in"
        >
          <div className="flex items-center justify-between pb-1.5 border-b border-slate-100">
            <span className="font-bold text-slate-800 truncate">
              Field: {chipPopover.fieldName}
            </span>
            <button onClick={onCloseChipPopover} className="text-slate-400 hover:text-slate-600">
              ✕
            </button>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Label</label>
            <input
              type="text"
              value={chipPopover.label}
              onChange={(e) => onUpdateChip({ label: e.target.value })}
              className="w-full px-2 py-1 border border-slate-200 rounded text-xs"
            />
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] font-semibold text-slate-600">Importance</span>
            <button
              onClick={() => onToggleChipRequired(!chipPopover.required)}
              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider transition ${
                chipPopover.required
                  ? 'bg-rose-100 text-rose-700 border border-rose-300'
                  : 'bg-slate-100 text-slate-600'
              }`}
            >
              {chipPopover.required ? 'Essential' : 'Optional'}
            </button>
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] font-semibold text-slate-600">Sensitive</span>
            <button
              onClick={() => onToggleChipSensitive(!chipPopover.sensitive)}
              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider transition flex items-center gap-1 ${
                chipPopover.sensitive
                  ? 'bg-amber-100 text-amber-800 border border-amber-300'
                  : 'bg-slate-100 text-slate-600'
              }`}
            >
              <Lock className="w-2.5 h-2.5" />
              {chipPopover.sensitive ? 'Yes' : 'No'}
            </button>
          </div>

          <div className="pt-2 border-t border-slate-100 flex justify-between items-center">
            <button
              onClick={onDeleteChip}
              className="text-rose-600 hover:text-rose-700 flex items-center gap-1 text-[11px] font-semibold"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Remove Chip
            </button>
            <button
              onClick={onCloseChipPopover}
              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded font-semibold text-[11px]"
            >
              Done
            </button>
          </div>
        </div>
      )}

      {/* Main A4 Document Sheet */}
      <A4Page
        zoom={zoom}
        watermarkText={watermarkText}
        orientation={orientation}
        margins={margins}
      >
        <EditorContent editor={editor} className="tiptap-editor-canvas focus:outline-none" />
      </A4Page>

      {/* Bottom Floating Stats Bar */}
      <div className="sticky bottom-3 z-20 flex items-center gap-3 px-3.5 py-1.5 bg-white/90 backdrop-blur border border-slate-200/80 rounded-full shadow-lg text-[11px] font-medium text-slate-600 select-none">
        <span>{wordCount} words</span>
        <span className="text-slate-300">•</span>
        <span>{charCount} characters</span>
        <span className="text-slate-300">•</span>
        <span>{blockCount} blocks</span>
      </div>
    </div>
  );
};
