import React, { useState } from 'react';
import {
  Heading1,
  Heading2,
  Heading3,
  Pilcrow,
  Table,
  Rows,
  CheckSquare,
  Minus,
  ChevronLeft,
  ChevronRight,
  GripVertical,
  Wand2,
  Tag,
  Palette,
  Layers,
  FileText,
} from 'lucide-react';
import {
  insertInfoTable,
  insertRepeatingTable,
  insertSignatureGrid,
  insertImageBlock,
  safeInsertBlock,
} from './extensions';
import { FieldsPanel, TemplateField } from './FieldsPanel';
import { DesignPanel, DesignSettings } from './DesignPanel';

export type LeftSidebarTab = 'blocks' | 'fields' | 'design';

interface PalettePanelProps {
  editor: any;
  isOpen: boolean;
  onToggle: () => void;
  fields?: TemplateField[];
  onAddField?: (field: TemplateField) => void;
  designSettings?: DesignSettings;
  onDesignChange?: (settings: Partial<DesignSettings>) => void;
  onAutoStyle?: () => void;
  sampleValues?: Record<string, string>;
  onSampleChange?: (key: string, value: string) => void;
  onPreview?: () => void;
  initialTab?: LeftSidebarTab;
}

export const PalettePanel: React.FC<PalettePanelProps> = ({
  editor,
  isOpen,
  onToggle,
  fields = [],
  onAddField = () => {},
  designSettings,
  onDesignChange = () => {},
  onAutoStyle,
  sampleValues = {},
  onSampleChange,
  onPreview,
  initialTab = 'blocks',
}) => {
  const [activeTab, setActiveTab] = useState<LeftSidebarTab>(initialTab);

  const handleDragStart = (e: React.DragEvent, blockType: string, customPayload?: any) => {
    e.dataTransfer.setData('text/plain', blockType);
    e.dataTransfer.setData('application/x-clubdocs-block', JSON.stringify({ type: blockType, ...customPayload }));
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handleInsertHeading = (level: 1 | 2 | 3) => {
    if (!editor) return;
    editor.chain().focus().toggleHeading({ level }).run();
  };

  const handleInsertParagraph = () => {
    if (!editor) return;
    editor.chain().focus().setParagraph().run();
  };

  const handleInsertClause = (text: string) => {
    if (!editor) return;
    const clauseNode = {
      type: 'paragraph',
      attrs: { ai_suggested: false },
      content: [{ type: 'text', text }],
    };
    safeInsertBlock(editor, clauseNode);
  };

  const handleInsertDivider = () => {
    if (!editor) return;
    safeInsertBlock(editor, { type: 'pageBreak' });
  };

  if (!isOpen) {
    return (
      <aside className="hidden lg:flex border-r border-slate-200 bg-slate-50 flex-col items-center py-3 px-1 transition-all select-none">
        <button
          onClick={onToggle}
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200 transition"
          title="Expand Left Panel"
          aria-label="Expand sidebar"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
        <span
          className="text-[11px] font-bold text-slate-400 mt-6 select-none cursor-pointer flex items-center gap-1.5"
          style={{ writingMode: 'vertical-rl' }}
          onClick={onToggle}
        >
          <Layers className="w-3.5 h-3.5 text-brand-500" />
          Blocks & Design
        </span>
      </aside>
    );
  }

  return (
    <>
      {/* Mobile backdrop overlay */}
      <div
        className="lg:hidden fixed inset-0 bg-slate-900/50 backdrop-blur-xs z-40 transition-opacity"
        onClick={onToggle}
        aria-hidden="true"
      />
      <aside className="fixed inset-y-0 left-0 z-50 w-72 sm:w-80 bg-white shadow-2xl flex flex-col h-full lg:static lg:z-auto lg:h-[calc(100vh-53px)] lg:w-80 lg:shadow-none lg:border-r lg:border-slate-200 select-none transition-all">
      {/* Header with Navigation Tabs */}
      <div className="border-b border-slate-200 bg-slate-50/80 px-2 py-1.5 flex items-center justify-between">
        <div className="flex items-center gap-1 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab('blocks')}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg transition ${
              activeTab === 'blocks'
                ? 'bg-white text-brand-700 shadow-xs border border-slate-200/80 font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
            title="Content blocks and layout elements"
          >
            <Layers className="w-3.5 h-3.5 text-brand-600" />
            <span>Blocks</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('fields')}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg transition ${
              activeTab === 'fields'
                ? 'bg-white text-brand-700 shadow-xs border border-slate-200/80 font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
            title="Dynamic template fields"
          >
            <Tag className="w-3.5 h-3.5 text-brand-600" />
            <span>Fields</span>
            {fields.length > 0 && (
              <span className="text-[10px] font-mono px-1 rounded-full bg-slate-100 text-slate-600">
                {fields.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('design')}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg transition ${
              activeTab === 'design'
                ? 'bg-white text-brand-700 shadow-xs border border-slate-200/80 font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
            title="Page orientation, fonts, and theme"
          >
            <Palette className="w-3.5 h-3.5 text-brand-600" />
            <span>Design</span>
          </button>
        </div>

        <button
          type="button"
          onClick={onToggle}
          className="p-2 sm:p-1 min-w-[44px] min-h-[44px] sm:min-w-0 sm:min-h-0 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded transition"
          title="Collapse Panel"
          aria-label="Collapse sidebar"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      {/* Tab Contents */}
      <div className="flex-1 overflow-hidden relative">
        {activeTab === 'blocks' && (
          <div className="h-full overflow-y-auto p-3 space-y-4 text-xs bg-slate-50/50">
            {/* Typography */}
            <div>
              <div className="text-[11px] font-bold text-slate-400 mb-1.5 px-1 uppercase tracking-wider">
                Typography
              </div>
              <div className="space-y-1">
                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'heading1')}
                  onClick={() => handleInsertHeading(1)}
                  className="w-full flex items-center gap-2 p-2 rounded-xl bg-white border border-slate-200 hover:border-brand-300 hover:shadow-xs text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <Heading1 className="w-4 h-4 text-brand-600 shrink-0" />
                  <div className="min-w-0">
                    <span className="font-semibold text-slate-800 text-xs block truncate">Document Title</span>
                    <span className="text-[10px] text-slate-400 block truncate">Heading 1 (18pt)</span>
                  </div>
                </button>

                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'heading2')}
                  onClick={() => handleInsertHeading(2)}
                  className="w-full flex items-center gap-2 p-2 rounded-xl bg-white border border-slate-200 hover:border-brand-300 hover:shadow-xs text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <Heading2 className="w-4 h-4 text-brand-600 shrink-0" />
                  <div className="min-w-0">
                    <span className="font-semibold text-slate-800 text-xs block truncate">Section Header</span>
                    <span className="text-[10px] text-slate-400 block truncate">Heading 2 (14pt)</span>
                  </div>
                </button>

                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'heading3')}
                  onClick={() => handleInsertHeading(3)}
                  className="w-full flex items-center gap-2 p-2 rounded-xl bg-white border border-slate-200 hover:border-brand-300 hover:shadow-xs text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <Heading3 className="w-4 h-4 text-brand-600 shrink-0" />
                  <div className="min-w-0">
                    <span className="font-semibold text-slate-800 text-xs block truncate">Sub-section</span>
                    <span className="text-[10px] text-slate-400 block truncate">Heading 3 (12pt)</span>
                  </div>
                </button>

                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'paragraph')}
                  onClick={handleInsertParagraph}
                  className="w-full flex items-center gap-2 p-2 rounded-xl bg-white border border-slate-200 hover:border-brand-300 hover:shadow-xs text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <Pilcrow className="w-4 h-4 text-slate-600 shrink-0" />
                  <div className="min-w-0">
                    <span className="text-slate-700 text-xs font-semibold block truncate">Paragraph Text</span>
                    <span className="text-[10px] text-slate-400 block truncate">Standard body paragraph</span>
                  </div>
                </button>
              </div>
            </div>

            {/* Official Tables */}
            <div>
              <div className="text-[11px] font-bold text-slate-400 mb-1.5 px-1 uppercase tracking-wider">
                Official Tables
              </div>
              <div className="space-y-1">
                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'infoTable')}
                  onClick={() => insertInfoTable(editor)}
                  className="w-full flex items-center gap-2 p-2 rounded-xl bg-white border border-slate-200 hover:border-brand-300 hover:shadow-xs text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <Table className="w-4 h-4 text-emerald-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-slate-800 text-xs truncate">Info Table</div>
                    <div className="text-[10px] text-slate-500 truncate">2-Column key-value details</div>
                  </div>
                </button>

                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'repeatingTable')}
                  onClick={() => insertRepeatingTable(editor)}
                  className="w-full flex items-center gap-2 p-2 rounded-xl bg-white border border-slate-200 hover:border-brand-300 hover:shadow-xs text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <Rows className="w-4 h-4 text-emerald-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-slate-800 text-xs truncate">Repeating Table</div>
                    <div className="text-[10px] text-slate-500 truncate">Items / budget with sum total</div>
                  </div>
                </button>

                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'signatureGrid')}
                  onClick={() => insertSignatureGrid(editor, 2)}
                  className="w-full flex items-center gap-2 p-2 rounded-xl bg-white border border-slate-200 hover:border-brand-300 hover:shadow-xs text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <CheckSquare className="w-4 h-4 text-amber-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-slate-800 text-xs truncate">Signature Grid</div>
                    <div className="text-[10px] text-slate-500 truncate">2-Column official sign-off</div>
                  </div>
                </button>
              </div>
            </div>

            {/* Layout & Assets (keeps only club logo and college logo as required) */}
            <div>
              <div className="text-[11px] font-bold text-slate-400 mb-1.5 px-1 uppercase tracking-wider">
                Layout & Assets
              </div>
              <div className="space-y-1">
                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'clubLogo')}
                  onClick={() => insertImageBlock(editor, { imageType: 'club-logo', alt: 'Club logo' })}
                  className="w-full flex items-center gap-2 p-2 rounded-xl bg-white border border-slate-200 hover:border-brand-300 hover:shadow-xs text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <Wand2 className="w-4 h-4 text-brand-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="font-semibold text-slate-800 text-xs block truncate">Club Logo</span>
                    <span className="text-[10px] text-slate-500 block truncate">Official club emblem</span>
                  </div>
                </button>

                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'collegeLogo')}
                  onClick={() => insertImageBlock(editor, { imageType: 'college-logo', alt: 'College logo', width: '90px' })}
                  className="w-full flex items-center gap-2 p-2 rounded-xl bg-white border border-slate-200 hover:border-brand-300 hover:shadow-xs text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <img src="/brand/svnit_crest.png" alt="" className="w-4 h-4 object-contain shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="font-semibold text-slate-800 text-xs block truncate">College Logo</span>
                    <span className="text-[10px] text-slate-500 block truncate">SVNIT Institute crest</span>
                  </div>
                </button>

                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'pageBreak')}
                  onClick={handleInsertDivider}
                  className="w-full flex items-center gap-2 p-2 rounded-xl bg-white border border-slate-200 hover:border-brand-300 hover:shadow-xs text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <Minus className="w-4 h-4 text-slate-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="text-slate-700 text-xs font-semibold block truncate">Page Break</span>
                    <span className="text-[10px] text-slate-500 block truncate">Start new printed page</span>
                  </div>
                </button>
              </div>
            </div>

            {/* SVNIT Preset Clauses */}
            <div>
              <div className="text-[11px] font-bold text-slate-400 mb-1.5 px-1 uppercase tracking-wider">
                Official SVNIT Clauses
              </div>
              <div className="space-y-1.5">
                <div
                  onClick={() =>
                    handleInsertClause(
                      'It is certified that the above expenditure was incurred in the interest of the institute/club and the rates are reasonable.'
                    )
                  }
                  className="p-2.5 rounded-xl bg-white border border-slate-200 hover:border-brand-400 hover:shadow-xs cursor-pointer transition select-none"
                  title="Click to insert clause"
                >
                  <div className="font-semibold text-slate-800 text-xs mb-0.5 flex items-center gap-1">
                    <FileText className="w-3 h-3 text-brand-600" />
                    <span>Expenditure Certification</span>
                  </div>
                  <div className="text-[10px] text-slate-500 line-clamp-2">
                    &ldquo;It is certified that the above expenditure was incurred in the interest of the institute...&rdquo;
                  </div>
                </div>

                <div
                  onClick={() =>
                    handleInsertClause(
                      'Submitted for kind approval and administrative sanction please.'
                    )
                  }
                  className="p-2.5 rounded-xl bg-white border border-slate-200 hover:border-brand-400 hover:shadow-xs cursor-pointer transition select-none"
                  title="Click to insert clause"
                >
                  <div className="font-semibold text-slate-800 text-xs mb-0.5 flex items-center gap-1">
                    <FileText className="w-3 h-3 text-brand-600" />
                    <span>Sanction Request</span>
                  </div>
                  <div className="text-[10px] text-slate-500 line-clamp-2">
                    &ldquo;Submitted for kind approval and administrative sanction please.&rdquo;
                  </div>
                </div>

                <div
                  onClick={() =>
                    handleInsertClause(
                      'The students and organizing committee undertake to maintain discipline and institute decorum during the event.'
                    )
                  }
                  className="p-2.5 rounded-xl bg-white border border-slate-200 hover:border-brand-400 hover:shadow-xs cursor-pointer transition select-none"
                  title="Click to insert clause"
                >
                  <div className="font-semibold text-slate-800 text-xs mb-0.5 flex items-center gap-1">
                    <FileText className="w-3 h-3 text-brand-600" />
                    <span>Discipline Undertaking</span>
                  </div>
                  <div className="text-[10px] text-slate-500 line-clamp-2">
                    &ldquo;The students and organizing committee undertake to maintain discipline...&rdquo;
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'fields' && (
          <FieldsPanel
            fields={fields}
            onAddField={onAddField}
            editor={editor}
            sampleValues={sampleValues}
            onSampleChange={onSampleChange}
            onPreview={onPreview}
          />
        )}

        {activeTab === 'design' && designSettings && (
          <DesignPanel
            settings={designSettings}
            onChange={onDesignChange}
            onAutoStyle={onAutoStyle}
          />
        )}
      </div>
    </aside>
    </>
  );
};
