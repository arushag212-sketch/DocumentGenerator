import React, { useState, useEffect } from 'react';
import {
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Plus,
  Trash2,
  Combine,
  Split,
} from 'lucide-react';
import { getTableDetails, moveTableRow, moveTableColumn, TableStateDetails } from './tableHelper';

interface TableControlsProps {
  editor: any;
}

export const TableControls: React.FC<TableControlsProps> = ({ editor }) => {
  const [details, setDetails] = useState<TableStateDetails | null>(null);

  useEffect(() => {
    if (!editor) return;

    const updateDetails = () => {
      setDetails(getTableDetails(editor));
    };

    updateDetails();
    editor.on('selectionUpdate', updateDetails);
    editor.on('update', updateDetails);

    return () => {
      editor.off('selectionUpdate', updateDetails);
      editor.off('update', updateDetails);
    };
  }, [editor]);

  if (!details || !details.isInsideTable) return null;

  return (
    <div className="sticky top-2 z-20 mx-auto mb-2 flex flex-wrap items-center gap-1 bg-white/95 backdrop-blur border border-slate-300 rounded-lg shadow-md px-2.5 py-1 text-xs select-none animate-in fade-in max-w-fit">
      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mr-1">
        Table (Row {details.rowIndex + 1}/{details.rowCount}, Col {details.colIndex + 1}/{details.colCount})
      </span>

      {/* Row reorder */}
      <div className="flex items-center gap-0.5 border-r border-slate-200 pr-1.5">
        <button
          onClick={() => moveTableRow(editor, 'up')}
          disabled={!details.canMoveRowUp}
          className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-30 disabled:hover:bg-transparent transition flex items-center gap-0.5 text-[11px]"
          title="Move row up"
        >
          <ArrowUp className="w-3 h-3" />
          <span>Row</span>
        </button>
        <button
          onClick={() => moveTableRow(editor, 'down')}
          disabled={!details.canMoveRowDown}
          className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-30 disabled:hover:bg-transparent transition flex items-center gap-0.5 text-[11px]"
          title="Move row down"
        >
          <ArrowDown className="w-3 h-3" />
          <span>Row</span>
        </button>
      </div>

      {/* Col reorder */}
      <div className="flex items-center gap-0.5 border-r border-slate-200 pr-1.5">
        <button
          onClick={() => moveTableColumn(editor, 'left')}
          disabled={!details.canMoveColLeft}
          className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-30 disabled:hover:bg-transparent transition flex items-center gap-0.5 text-[11px]"
          title="Move column left"
        >
          <ArrowLeft className="w-3 h-3" />
          <span>Col</span>
        </button>
        <button
          onClick={() => moveTableColumn(editor, 'right')}
          disabled={!details.canMoveColRight}
          className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-30 disabled:hover:bg-transparent transition flex items-center gap-0.5 text-[11px]"
          title="Move column right"
        >
          <ArrowRight className="w-3 h-3" />
          <span>Col</span>
        </button>
      </div>

      {/* Row add/delete */}
      <div className="flex items-center gap-0.5 border-r border-slate-200 pr-1.5">
        <button
          onClick={() => editor.chain().focus().addRowAfter().run()}
          className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition flex items-center gap-0.5 text-[11px]"
          title="Add row below"
        >
          <Plus className="w-3 h-3" />
          <span>Row</span>
        </button>
        <button
          onClick={() => editor.chain().focus().deleteRow().run()}
          className="p-1 rounded text-rose-600 hover:text-rose-700 hover:bg-rose-50 transition flex items-center gap-0.5 text-[11px]"
          title="Delete current row"
        >
          <Trash2 className="w-3 h-3" />
          <span>Row</span>
        </button>
      </div>

      {/* Col add/delete */}
      <div className="flex items-center gap-0.5 border-r border-slate-200 pr-1.5">
        <button
          onClick={() => editor.chain().focus().addColumnAfter().run()}
          className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition flex items-center gap-0.5 text-[11px]"
          title="Add column right"
        >
          <Plus className="w-3 h-3" />
          <span>Col</span>
        </button>
        <button
          onClick={() => editor.chain().focus().deleteColumn().run()}
          className="p-1 rounded text-rose-600 hover:text-rose-700 hover:bg-rose-50 transition flex items-center gap-0.5 text-[11px]"
          title="Delete current column"
        >
          <Trash2 className="w-3 h-3" />
          <span>Col</span>
        </button>
      </div>

      {/* Merge / Split */}
      <div className="flex items-center gap-0.5">
        <button
          onClick={() => editor.chain().focus().mergeCells().run()}
          disabled={!details.canMerge}
          className="p-1 rounded text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 disabled:opacity-30 disabled:hover:bg-transparent transition flex items-center gap-0.5 text-[11px]"
          title="Merge selected cells"
        >
          <Combine className="w-3 h-3" />
          <span>Merge</span>
        </button>
        <button
          onClick={() => editor.chain().focus().splitCell().run()}
          disabled={!details.canSplit}
          className="p-1 rounded text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 disabled:opacity-30 disabled:hover:bg-transparent transition flex items-center gap-0.5 text-[11px]"
          title="Split merged cell"
        >
          <Split className="w-3 h-3" />
          <span>Split</span>
        </button>
      </div>
    </div>
  );
};
