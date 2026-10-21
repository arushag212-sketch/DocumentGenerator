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
  Table as TableIcon,
  Rows,
  CheckSquare,
  SplitSquareVertical,
  Heading1,
  Heading2,
  Wand2,
  Search,
  Plus,
  Tag,
  Lock,
} from 'lucide-react';
import { EditorContextMenu } from './EditorContextMenu';
import { FontControls } from './FontControls';
import { A4Page } from './A4Page';
import { ChipPopover } from './ChipPopover';
import { TableControls } from './TableControls';
import { BlockDragHandle } from './BlockDragHandle';
import { ImageBlockPopover } from './ImageBlockPopover';
import { createImageBlockNode } from './imageBlock';
import {
  insertInfoTable,
  insertRepeatingTable,
  insertSignatureGrid,
  insertFieldChip,
  safeInsertBlock,
} from './extensions';
import { DesignSettings } from './DesignPanel';
import { TemplateField } from './FieldsPanel';
import { InlinePickerState } from './useTemplateEditor';

interface CanvasProps {
  editor: any;
  zoom: number;
  watermarkText?: string;
  orientation?: 'portrait' | 'landscape';
  margins?: 'normal' | 'compact' | 'wide';
  designSettings?: DesignSettings;
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
  fields?: TemplateField[];
  inlinePicker?: InlinePickerState | null;
  onCloseInlinePicker?: () => void;
  onAddNewField?: (field: TemplateField) => void;
  /** The printed letterhead and footer, so the page looks as it will be generated */
  letterhead?: { header?: React.ReactNode; footer?: React.ReactNode };
}

export const Canvas: React.FC<CanvasProps> = ({
  editor,
  zoom,
  watermarkText,
  orientation = 'portrait',
  margins = 'normal',
  designSettings,
  bubblePos,
  chipPopover,
  onCloseChipPopover,
  onUpdateChip,
  onToggleChipRequired,
  onToggleChipSensitive,
  onDeleteChip,
  selectedImageBlock,
  onUpdateImageBlock,
  clubLogoOptions = [],
  showSlashMenu,
  onCloseSlashMenu,
  onOpenAddField,
  fields = [],
  inlinePicker,
  onCloseInlinePicker = () => {},
  onAddNewField = () => {},
  letterhead,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [wordCount, setWordCount] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const [blockCount, setBlockCount] = useState(0);
  const [fieldSearch, setFieldSearch] = useState('');

  // Inline new field form state
  const [showInlineNewField, setShowInlineNewField] = useState(false);
  const [newLabel, setNewLabel] = useState('');
  const [newType, setNewType] = useState('text');
  const [newRequired, setNewRequired] = useState(true);

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
      title: 'Dynamic Field ({{)',
      icon: <Wand2 className="w-4 h-4 text-brand-600" />,
      action: () => {
        if (inlinePicker?.range) {
          editor?.chain().focus().deleteRange(inlinePicker.range).run();
        } else {
          editor?.chain().focus().deleteRange({ from: editor.state.selection.from - 1, to: editor.state.selection.from }).run();
        }
        onOpenAddField();
        onCloseSlashMenu();
        onCloseInlinePicker();
      },
    },
    {
      title: 'Heading 1',
      icon: <Heading1 className="w-4 h-4 text-brand-600" />,
      action: () => {
        const range = inlinePicker?.range || { from: editor.state.selection.from - 1, to: editor.state.selection.from };
        editor?.chain().focus().deleteRange(range).setHeading({ level: 1 }).run();
        onCloseSlashMenu();
        onCloseInlinePicker();
      },
    },
    {
      title: 'Heading 2',
      icon: <Heading2 className="w-4 h-4 text-brand-600" />,
      action: () => {
        const range = inlinePicker?.range || { from: editor.state.selection.from - 1, to: editor.state.selection.from };
        editor?.chain().focus().deleteRange(range).setHeading({ level: 2 }).run();
        onCloseSlashMenu();
        onCloseInlinePicker();
      },
    },
    {
      title: 'Info Table (Key-Value)',
      icon: <TableIcon className="w-4 h-4 text-emerald-600" />,
      action: () => {
        const range = inlinePicker?.range || { from: editor.state.selection.from - 1, to: editor.state.selection.from };
        editor?.chain().focus().deleteRange(range).run();
        insertInfoTable(editor);
        onCloseSlashMenu();
        onCloseInlinePicker();
      },
    },
    {
      title: 'Repeating Table (Items & Sum)',
      icon: <Rows className="w-4 h-4 text-brand-600" />,
      action: () => {
        const range = inlinePicker?.range || { from: editor.state.selection.from - 1, to: editor.state.selection.from };
        editor?.chain().focus().deleteRange(range).run();
        insertRepeatingTable(editor);
        onCloseSlashMenu();
        onCloseInlinePicker();
      },
    },
    {
      title: 'Signature Grid (Signatures)',
      icon: <CheckSquare className="w-4 h-4 text-amber-600" />,
      action: () => {
        const range = inlinePicker?.range || { from: editor.state.selection.from - 1, to: editor.state.selection.from };
        editor?.chain().focus().deleteRange(range).run();
        insertSignatureGrid(editor, 2);
        onCloseSlashMenu();
        onCloseInlinePicker();
      },
    },
    {
      title: 'Page Break',
      icon: <SplitSquareVertical className="w-4 h-4 text-rose-500" />,
      action: () => {
        const range = inlinePicker?.range || { from: editor.state.selection.from - 1, to: editor.state.selection.from };
        editor?.chain().focus().deleteRange(range).insertContent({ type: 'pageBreak' }).run();
        onCloseSlashMenu();
        onCloseInlinePicker();
      },
    },
  ];

  const handleSelectFieldInline = (field: TemplateField) => {
    if (!editor) return;
    if (inlinePicker?.range) {
      editor.chain().focus().deleteRange(inlinePicker.range).run();
    }
    insertFieldChip(
      editor,
      field.key,
      field.label,
      field.type,
      field.ask || `Please enter ${field.label}`,
      field.required ? 'essential' : 'optional',
      field.required,
      field.sensitive || false
    );
    onCloseInlinePicker();
    setFieldSearch('');
    setShowInlineNewField(false);
  };

  const handleCreateFieldInline = (e: React.FormEvent) => {
    e.preventDefault();
    const label = newLabel.trim();
    if (!label) return;

    let key = label.toLowerCase().replace(/[^a-z0-9_]/g, '_');
    if (!/^[a-z]/.test(key)) key = `field_${key}`;

    const newField: TemplateField = {
      key,
      label,
      type: newType,
      required: newRequired,
      importance: newRequired ? 'essential' : 'optional',
      ask: `Please enter ${label}`,
    };

    onAddNewField(newField);
    handleSelectFieldInline(newField);
    setNewLabel('');
    setShowInlineNewField(false);
  };

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
        else if (parsed.type === 'clubLogo') safeInsertBlock(editor, createImageBlockNode({ imageType: 'club-logo', alt: 'Club logo' }));
        else if (parsed.type === 'pageBreak') safeInsertBlock(editor, { type: 'pageBreak' });
      } catch (err) {
        console.error('Failed to drop block:', err);
      }
    }
  };

  const filteredFieldsInline = fields.filter(
    (f) =>
      f.label.toLowerCase().includes(fieldSearch.toLowerCase()) ||
      f.key.toLowerCase().includes(fieldSearch.toLowerCase())
  );

  return (
    <div
      ref={containerRef}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      className="relative flex-1 bg-slate-100 overflow-auto flex flex-col items-center select-text"
    >
      {/* Floating Selection Bubble Menu */}
      {bubblePos && editor && (
        <div
          data-editor-bubble
          style={{ top: `${bubblePos.top}px`, left: `${bubblePos.left}px` }}
          className="fixed z-40 flex items-center gap-0.5 bg-slate-900/95 backdrop-blur text-white px-1.5 py-1 rounded-lg shadow-xl border border-slate-700 animate-in fade-in zoom-in-95 duration-100"
        >
          <button
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive('bold') ? 'text-brand-500 bg-slate-800' : 'text-slate-200'}`}
            title="Bold"
          >
            <Bold className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive('italic') ? 'text-brand-500 bg-slate-800' : 'text-slate-200'}`}
            title="Italic"
          >
            <Italic className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive('underline') ? 'text-brand-500 bg-slate-800' : 'text-slate-200'}`}
            title="Underline"
          >
            <UnderlineIcon className="w-3.5 h-3.5" />
          </button>

          <div className="w-px h-3.5 bg-slate-700 mx-0.5" />

          <FontControls variant="bubble" editor={editor} />

          <div className="w-px h-3.5 bg-slate-700 mx-0.5" />

          <button
            onClick={() => editor.chain().focus().setTextAlign('left').run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive({ textAlign: 'left' }) ? 'text-brand-500 bg-slate-800' : 'text-slate-200'}`}
            title="Align Left"
          >
            <AlignLeft className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().setTextAlign('center').run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive({ textAlign: 'center' }) ? 'text-brand-500 bg-slate-800' : 'text-slate-200'}`}
            title="Align Center"
          >
            <AlignCenter className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().setTextAlign('right').run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive({ textAlign: 'right' }) ? 'text-brand-500 bg-slate-800' : 'text-slate-200'}`}
            title="Align Right"
          >
            <AlignRight className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => editor.chain().focus().setTextAlign('justify').run()}
            className={`p-1 rounded hover:bg-slate-800 ${editor.isActive({ textAlign: 'justify' }) ? 'text-brand-500 bg-slate-800' : 'text-slate-200'}`}
            title="Justify"
          >
            <AlignJustify className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Inline Field Picker (triggered by typing '{{') */}
      {inlinePicker && inlinePicker.type === 'field' && (
        <div
          style={{ top: `${inlinePicker.top}px`, left: `${inlinePicker.left}px` }}
          className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-2xl w-72 p-2 animate-in fade-in zoom-in-95"
        >
          {!showInlineNewField ? (
            <>
              <div className="flex items-center gap-1.5 px-2 py-1 mb-1.5 border-b border-slate-100">
                <Tag className="w-3.5 h-3.5 text-brand-600" />
                <span className="font-bold text-slate-800 text-xs">Insert Field</span>
              </div>

              <div className="relative mb-2">
                <Search className="w-3 h-3 text-slate-400 absolute left-2 top-2" />
                <input
                  type="text"
                  value={fieldSearch}
                  onChange={(e) => setFieldSearch(e.target.value)}
                  placeholder="Filter fields…"
                  className="w-full text-xs pl-7 pr-2 py-1 border border-slate-200 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
                  autoFocus
                />
              </div>

              <div className="max-h-48 overflow-y-auto space-y-0.5">
                {filteredFieldsInline.length === 0 ? (
                  <div className="text-center py-3 text-slate-400 text-xs">
                    No matching fields.
                  </div>
                ) : (
                  filteredFieldsInline.map((f) => (
                    <button
                      key={f.key}
                      onClick={() => handleSelectFieldInline(f)}
                      className="w-full flex items-center justify-between p-1.5 rounded-lg text-left text-xs hover:bg-brand-50 hover:text-brand-800 transition"
                    >
                      <div className="min-w-0">
                        <span className="font-semibold text-slate-800 block truncate">{f.label}</span>
                        <span className="text-[10px] font-mono text-slate-400 block truncate">{`{{ ${f.key} }}`}</span>
                      </div>
                      <span className="text-[9px] uppercase px-1 py-0.5 rounded bg-slate-100 text-slate-500 font-medium shrink-0">
                        {f.type}
                      </span>
                    </button>
                  ))
                )}
              </div>

              <div className="pt-2 mt-1 border-t border-slate-100 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowInlineNewField(true)}
                  className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700 font-semibold px-1 py-0.5 rounded transition"
                >
                  <Plus className="w-3 h-3" />
                  <span>Create new field</span>
                </button>
                <button
                  type="button"
                  onClick={onCloseInlinePicker}
                  className="text-xs text-slate-400 hover:text-slate-600 px-1 py-0.5"
                >
                  Cancel
                </button>
              </div>
            </>
          ) : (
            <form onSubmit={handleCreateFieldInline} className="p-1 space-y-2 text-xs">
              <div className="font-bold text-slate-800 pb-1 border-b border-slate-100">
                New Template Field
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-0.5">Label</label>
                <input
                  type="text"
                  value={newLabel}
                  onChange={(e) => setNewLabel(e.target.value)}
                  placeholder="e.g. Venue"
                  className="w-full text-xs px-2 py-1 border border-slate-300 rounded focus:ring-1 focus:ring-brand-500 focus:outline-none"
                  autoFocus
                  required
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-0.5">Type</label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  className="w-full text-xs px-2 py-1 border border-slate-300 rounded focus:ring-1 focus:ring-brand-500 focus:outline-none"
                >
                  <option value="text">Text</option>
                  <option value="date">Date</option>
                  <option value="time">Time</option>
                  <option value="money">Money (INR)</option>
                  <option value="number">Number</option>
                </select>
              </div>

              <label className="flex items-center gap-1.5 cursor-pointer pt-0.5">
                <input
                  type="checkbox"
                  checked={newRequired}
                  onChange={(e) => setNewRequired(e.target.checked)}
                  className="rounded border-slate-300 text-brand-600"
                />
                <span className="text-[11px] text-slate-700">Required field</span>
              </label>

              <div className="flex justify-end gap-1.5 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowInlineNewField(false)}
                  className="px-2 py-1 text-slate-500 hover:bg-slate-100 rounded text-xs"
                >
                  Back
                </button>
                <button
                  type="submit"
                  className="px-3 py-1 bg-brand-600 hover:bg-brand-700 text-white rounded text-xs font-semibold"
                >
                  Insert
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Slash Command Popover Menu (triggered by typing '/') */}
      {(showSlashMenu || (inlinePicker && inlinePicker.type === 'slash')) && (
        <div
          style={
            inlinePicker
              ? { top: `${inlinePicker.top}px`, left: `${inlinePicker.left}px` }
              : undefined
          }
          className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-2xl w-64 p-1.5 animate-in fade-in zoom-in-95"
        >
          <div className="text-[11px] font-bold text-slate-400 px-2 py-1 uppercase tracking-wider">
            Insert Block
          </div>
          <div className="space-y-0.5">
            {slashItems.map((item, idx) => (
              <button
                key={idx}
                onClick={item.action}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-xs text-slate-700 hover:bg-brand-50 hover:text-brand-700 transition"
              >
                {item.icon}
                <span className="font-medium">{item.title}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Right-click menu (replaces the browser's) */}
      <EditorContextMenu editor={editor} containerRef={containerRef as React.RefObject<HTMLElement>} />

      {/* Field Chip Edit Popover */}
      <ChipPopover
        chipPopover={chipPopover}
        onClose={onCloseChipPopover}
        onUpdateChip={onUpdateChip}
        onToggleRequired={onToggleChipRequired}
        onToggleSensitive={onToggleChipSensitive}
        onDelete={onDeleteChip}
      />

      {/* Selected Image Block Settings Popover */}
      <ImageBlockPopover
        selectedBlock={selectedImageBlock}
        onUpdate={onUpdateImageBlock}
        onClose={() => onUpdateImageBlock(null)}
        clubLogoOptions={clubLogoOptions}
        editor={editor}
      />

      {/* Floating Table Controls when inside table */}
      <TableControls editor={editor} />

      {/* Block Drag Handle and Alt+Up/Down keyboard hints */}
      <BlockDragHandle editor={editor} containerRef={containerRef} />

      {/* Main A4 Document Sheet */}
      <A4Page
        zoom={zoom}
        watermarkText={designSettings?.watermark || watermarkText}
        watermarkOpacity={designSettings?.watermarkOpacity}
        orientation={designSettings?.orientation || orientation}
        margins={designSettings?.margins || margins}
        pageBg={designSettings?.pageBg}
        pageBorder={designSettings?.pageBorder}
        borderColor={designSettings?.borderColor}
        layout={designSettings?.layout}
        headingColor={designSettings?.headingColor}
        textColor={designSettings?.textColor}
        fontFamily={designSettings?.fontFamily}
        headingFontFamily={designSettings?.headingFontFamily}
        tableHeaderBg={designSettings?.tableHeaderBg}
        tableHeaderTextColor={designSettings?.tableHeaderTextColor}
        header={
          <div className="relative mb-4 group select-none">
            <div className="flex items-center justify-between px-2.5 py-1 mb-1.5 rounded-md bg-slate-100/90 border border-slate-200/80 text-[11px] text-slate-500 font-medium select-none">
              <span className="flex items-center gap-1.5 font-semibold text-slate-700">
                <Lock className="w-3 h-3 text-slate-400" />
                Club letterhead — edit in Club Settings
              </span>
              <span className="text-[10px] text-slate-400">Locked area</span>
            </div>
            {letterhead?.header}
          </div>
        }
        footer={letterhead?.footer}
      >
        <EditorContent editor={editor} className="tiptap-editor-canvas focus:outline-none" />
      </A4Page>

      {/* Bottom Floating Stats Bar */}
      <div className="sticky bottom-3 z-20 flex items-center gap-3 px-3.5 py-1.5 bg-white/90 backdrop-blur border border-slate-200/80 rounded-full shadow-lg text-xs font-medium text-slate-600 select-none">
        <span>{wordCount} words</span>
        <span className="text-slate-300">•</span>
        <span>{charCount} characters</span>
        <span className="text-slate-300">•</span>
        <span>{blockCount} blocks</span>
      </div>
    </div>
  );
};
