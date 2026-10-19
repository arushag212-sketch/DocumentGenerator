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
  Sparkles,
  ChevronLeft,
  ChevronRight,
  GripVertical,
} from 'lucide-react';
import {
  insertInfoTable,
  insertRepeatingTable,
  insertSignatureGrid,
  insertImageBlock,
  safeInsertBlock,
} from './extensions';

interface PalettePanelProps {
  editor: any;
  isOpen: boolean;
  onToggle: () => void;
  clubLogoOptions?: Array<{ id: string; name: string; url: string; kind?: string }>;
}

export const PalettePanel: React.FC<PalettePanelProps> = ({
  editor,
  isOpen,
  onToggle,
  clubLogoOptions = [],
}) => {
  const [activeCategory, setActiveCategory] = useState<'blocks' | 'clauses'>('blocks');

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
    const pageBreakNode = { type: 'pageBreak' };
    safeInsertBlock(editor, pageBreakNode);
  };

  if (!isOpen) {
    return (
      <aside className="border-r border-slate-200 bg-slate-50 flex flex-col items-center py-3 px-1 transition-all">
        <button
          onClick={onToggle}
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200 transition"
          title="Expand Blocks Palette"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
        <span
          className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-6 select-none cursor-pointer"
          style={{ writingMode: 'vertical-rl' }}
          onClick={onToggle}
        >
          Blocks Palette
        </span>
      </aside>
    );
  }

  return (
    <aside className="w-64 border-r border-slate-200 bg-slate-50/70 flex flex-col h-[calc(100vh-53px)] select-none transition-all">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-200 bg-white">
        <span className="font-bold text-slate-800 text-xs tracking-wide uppercase">
          Blocks Palette
        </span>
        <button
          onClick={onToggle}
          className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded transition"
          title="Collapse Palette"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 bg-slate-100 p-1 gap-1 text-[11px] font-semibold">
        <button
          onClick={() => setActiveCategory('blocks')}
          className={`flex-1 py-1 rounded transition text-center ${
            activeCategory === 'blocks'
              ? 'bg-white text-indigo-700 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Blocks
        </button>
        <button
          onClick={() => setActiveCategory('clauses')}
          className={`flex-1 py-1 rounded transition text-center ${
            activeCategory === 'clauses'
              ? 'bg-white text-indigo-700 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Preset Clauses
        </button>
      </div>

      {/* Scrollable Items */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4 text-xs">
        {activeCategory === 'blocks' ? (
          <>
            {/* Typography */}
            <div>
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5 px-1">
                Typography
              </div>
              <div className="space-y-1">
                <button
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'heading1')}
                  onClick={() => handleInsertHeading(1)}
                  className="w-full flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500" />
                  <Heading1 className="w-4 h-4 text-indigo-600" />
                  <span className="font-semibold text-slate-800 text-xs">Title (Heading 1)</span>
                </button>

                <button
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'heading2')}
                  onClick={() => handleInsertHeading(2)}
                  className="w-full flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500" />
                  <Heading2 className="w-4 h-4 text-indigo-600" />
                  <span className="font-semibold text-slate-800 text-xs">Section (Heading 2)</span>
                </button>

                <button
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'heading3')}
                  onClick={() => handleInsertHeading(3)}
                  className="w-full flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500" />
                  <Heading3 className="w-4 h-4 text-indigo-600" />
                  <span className="font-semibold text-slate-800 text-xs">Sub-section (Heading 3)</span>
                </button>

                <button
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'paragraph')}
                  onClick={handleInsertParagraph}
                  className="w-full flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500" />
                  <Pilcrow className="w-4 h-4 text-slate-600" />
                  <span className="text-slate-700 text-xs">Paragraph Text</span>
                </button>
              </div>
            </div>

            {/* Official Tables */}
            <div>
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5 px-1">
                Official Tables
              </div>
              <div className="space-y-1">
                <button
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'infoTable')}
                  onClick={() => insertInfoTable(editor)}
                  className="w-full flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500" />
                  <Table className="w-4 h-4 text-emerald-600" />
                  <div className="flex-1">
                    <div className="font-semibold text-slate-800 text-xs">Info Table</div>
                    <div className="text-[10px] text-slate-500">2-Column key-value details</div>
                  </div>
                </button>

                <button
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'repeatingTable')}
                  onClick={() => insertRepeatingTable(editor)}
                  className="w-full flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500" />
                  <Rows className="w-4 h-4 text-emerald-600" />
                  <div className="flex-1">
                    <div className="font-semibold text-slate-800 text-xs">Repeating Table</div>
                    <div className="text-[10px] text-slate-500">Items/budget with sum total</div>
                  </div>
                </button>

                <button
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'signatureGrid')}
                  onClick={() => insertSignatureGrid(editor, 2)}
                  className="w-full flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500" />
                  <CheckSquare className="w-4 h-4 text-amber-600" />
                  <div className="flex-1">
                    <div className="font-semibold text-slate-800 text-xs">Signature Grid</div>
                    <div className="text-[10px] text-slate-500">2-Column official sign-off</div>
                  </div>
                </button>
              </div>
            </div>

            {/* Layout & Assets */}
            <div>
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5 px-1">
                Layout & Assets
              </div>
              <div className="space-y-1">
                <button
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'clubLogo')}
                  onClick={() => insertImageBlock(editor, { imageType: 'club-logo', alt: 'Club logo' })}
                  className="w-full flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500" />
                  <Sparkles className="w-4 h-4 text-indigo-600" />
                  <span className="font-semibold text-slate-800 text-xs">Club Logo Block</span>
                </button>

                {clubLogoOptions.map((asset) => (
                  <button
                    key={asset.id}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData('text/plain', `[Logo: ${asset.name}]`);
                      e.dataTransfer.setData(
                        'application/x-clubdocs-asset',
                        JSON.stringify({
                          assetId: asset.id,
                          url: asset.url,
                          filename: asset.name,
                          kind: asset.kind,
                        })
                      );
                      e.dataTransfer.setData(
                        'application/x-clubdocs-block',
                        JSON.stringify({
                          type: 'imageBlock',
                          src: asset.url,
                          assetId: asset.id,
                          alt: asset.name,
                          imageType: asset.kind || 'club-logo',
                        })
                      );
                      e.dataTransfer.effectAllowed = 'copy';
                    }}
                    onClick={() =>
                      insertImageBlock(editor, {
                        src: asset.url,
                        assetId: asset.id,
                        imageType: asset.kind || 'club-logo',
                        alt: asset.name,
                      })
                    }
                    className="w-full flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm text-left transition group"
                  >
                    <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500" />
                    <Sparkles className="w-4 h-4 text-emerald-600" />
                    <div className="flex-1 truncate">
                      <div className="font-semibold text-slate-800 text-xs truncate">
                        {asset.name}
                      </div>
                      <div className="text-[10px] text-slate-500 uppercase">
                        {asset.kind || 'Logo'}
                      </div>
                    </div>
                  </button>
                ))}

                <button
                  draggable
                  onDragStart={(e) => handleDragStart(e, 'pageBreak')}
                  onClick={handleInsertDivider}
                  className="w-full flex items-center gap-2 p-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm text-left transition group"
                >
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500" />
                  <Minus className="w-4 h-4 text-slate-400" />
                  <span className="text-slate-700 text-xs">Page Break</span>
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="space-y-2">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5 px-1">
              Official SVNIT Clauses
            </div>

            <div
              onClick={() =>
                handleInsertClause(
                  'It is certified that the above expenditure was incurred in the interest of the institute/club and the rates are reasonable.'
                )
              }
              className="p-2.5 rounded-lg bg-white border border-slate-200 hover:border-indigo-400 hover:shadow-sm cursor-pointer transition"
            >
              <div className="font-semibold text-slate-800 text-xs mb-1">Expenditure Certification</div>
              <div className="text-[10px] text-slate-500 line-clamp-2">
                "It is certified that the above expenditure was incurred in the interest of the institute..."
              </div>
            </div>

            <div
              onClick={() =>
                handleInsertClause(
                  'Submitted for kind approval and administrative sanction please.'
                )
              }
              className="p-2.5 rounded-lg bg-white border border-slate-200 hover:border-indigo-400 hover:shadow-sm cursor-pointer transition"
            >
              <div className="font-semibold text-slate-800 text-xs mb-1">Sanction Request</div>
              <div className="text-[10px] text-slate-500 line-clamp-2">
                "Submitted for kind approval and administrative sanction please."
              </div>
            </div>

            <div
              onClick={() =>
                handleInsertClause(
                  'The students and organizing committee undertake to maintain discipline and institute decorum during the event.'
                )
              }
              className="p-2.5 rounded-lg bg-white border border-slate-200 hover:border-indigo-400 hover:shadow-sm cursor-pointer transition"
            >
              <div className="font-semibold text-slate-800 text-xs mb-1">Discipline Undertaking</div>
              <div className="text-[10px] text-slate-500 line-clamp-2">
                "The students and organizing committee undertake to maintain discipline..."
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
