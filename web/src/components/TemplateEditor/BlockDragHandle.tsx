import React, { useState, useEffect } from 'react';
import { NodeSelection } from '@tiptap/pm/state';
import {
  GripVertical,
  ArrowUp,
  ArrowDown,
  Copy,
  Trash2,
  Lock,
  MoreVertical,
  AlertCircle,
} from 'lucide-react';
import { isLockedNode, moveTopLevelBlock } from './blockDragDrop';

interface BlockDragHandleProps {
  editor: any;
  containerRef: React.RefObject<HTMLDivElement | null>;
}

export const BlockDragHandle: React.FC<BlockDragHandleProps> = ({ editor, containerRef }) => {
  const [handlePos, setHandlePos] = useState<{ top: number; left: number } | null>(null);
  const [hoveredRect, setHoveredRect] = useState<{ top: number; left: number; width: number; height: number } | null>(null);
  const [showMenu, setShowMenu] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [activeNodeInfo, setActiveNodeInfo] = useState<{
    pos: number;
    index: number;
    type: string;
    isLocked: boolean;
  } | null>(null);

  useEffect(() => {
    if (!editor || !containerRef.current) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!editor.view || !editor.view.dom) return;

      const editorDom = editor.view.dom as HTMLElement;
      const editorRect = editorDom.getBoundingClientRect();

      // Only show handle if within horizontal proximity of editor canvas
      if (e.clientX < editorRect.left - 70 || e.clientX > editorRect.right + 20) {
        return;
      }

      const coords = editor.view.posAtCoords({ left: editorRect.left + 20, top: e.clientY });
      if (!coords) return;

      const { doc } = editor.state;
      const $pos = doc.resolve(coords.pos);
      const topIndex = $pos.index(0);

      if (topIndex < 0 || topIndex >= doc.childCount) {
        return;
      }

      const node = doc.child(topIndex);
      let nodePos = 0;
      for (let i = 0; i < topIndex; i++) {
        nodePos += doc.child(i).nodeSize;
      }

      const domNode = editor.view.nodeDOM(nodePos) as HTMLElement | null;
      if (!domNode || typeof domNode.getBoundingClientRect !== 'function') return;

      const rect = domNode.getBoundingClientRect();
      const containerRect = containerRef.current?.getBoundingClientRect() || { top: 0, left: 0 };

      setHandlePos({
        top: rect.top - containerRect.top + 4,
        left: Math.max(10, rect.left - containerRect.left - 48),
      });

      setHoveredRect({
        top: rect.top - containerRect.top,
        left: rect.left - containerRect.left,
        width: rect.width,
        height: rect.height,
      });

      setActiveNodeInfo({
        pos: nodePos,
        index: topIndex,
        type: node.type.name,
        isLocked: isLockedNode(node),
      });
    };

    const container = containerRef.current;
    container.addEventListener('mousemove', handleMouseMove);

    return () => {
      container.removeEventListener('mousemove', handleMouseMove);
    };
  }, [editor, containerRef]);

  if (!handlePos || !activeNodeInfo) return null;

  const handleDragStart = (e: React.DragEvent) => {
    if (activeNodeInfo.isLocked) {
      e.preventDefault();
      return;
    }
    e.dataTransfer.setData(
      'application/x-clubdocs-block-drag',
      JSON.stringify({
        index: activeNodeInfo.index,
        pos: activeNodeInfo.pos,
      })
    );
    e.dataTransfer.effectAllowed = 'move';

    // Select the node so ProseMirror renders native drop indicators
    const { state, view } = editor;
    try {
      const sel = NodeSelection.create(state.doc, activeNodeInfo.pos);
      view.dispatch(state.tr.setSelection(sel));
    } catch {
      // Node may not be node-selectable; continue with HTML drag
    }
  };

  const handleDuplicate = () => {
    if (!editor || activeNodeInfo.isLocked) return;
    const { state, view } = editor;
    const node = state.doc.child(activeNodeInfo.index);
    const newAttrs = {
      ...node.attrs,
      blockId: `b_${Math.random().toString(36).substring(2, 9)}`,
    };
    const cloned = node.type.create(newAttrs, node.content, node.marks);
    const insertPos = activeNodeInfo.pos + node.nodeSize;
    view.dispatch(state.tr.insert(insertPos, cloned));
    setShowMenu(false);
  };

  const handleDelete = () => {
    if (!editor || activeNodeInfo.isLocked) return;
    const { state, view } = editor;
    const node = state.doc.child(activeNodeInfo.index);
    view.dispatch(state.tr.delete(activeNodeInfo.pos, activeNodeInfo.pos + node.nodeSize));
    setShowMenu(false);
    setConfirmDelete(false);
  };

  if (activeNodeInfo.isLocked) {
    return (
      <div
        style={{ top: `${handlePos.top}px`, left: `${handlePos.left}px` }}
        className="absolute z-30 flex items-center gap-1 bg-amber-50 border border-amber-300 text-amber-800 text-[11px] font-bold px-2 py-1 rounded-md shadow-xs select-none"
        title="SVNIT Letterhead Slot (Locked, cannot be moved or deleted)"
      >
        <Lock className="w-3 h-3 text-amber-600" />
        <span>Locked</span>
      </div>
    );
  }

  return (
    <>
      {/* Faint outline hovering around active block */}
      {hoveredRect && (
        <div
          style={{
            top: `${hoveredRect.top - 2}px`,
            left: `${hoveredRect.left - 4}px`,
            width: `${hoveredRect.width + 8}px`,
            height: `${hoveredRect.height + 4}px`,
          }}
          className="pointer-events-none absolute rounded-lg border border-brand-300/30 bg-brand-50/5 transition-all duration-75 z-10"
          aria-hidden="true"
        />
      )}

      {/* Floating block handle */}
      <div
        style={{ top: `${handlePos.top}px`, left: `${handlePos.left}px` }}
        className="absolute z-30 flex items-center gap-0.5 bg-white/95 backdrop-blur border border-slate-200 rounded-lg shadow-md p-0.5 select-none transition-all group"
      >
        {/* Drag handle grip */}
        <div
          draggable
          onDragStart={handleDragStart}
          className="p-1 rounded cursor-grab active:cursor-grabbing text-slate-400 hover:text-brand-600 hover:bg-brand-50 transition"
          title="Drag block to reorder"
          aria-label="Drag block to reorder"
        >
          <GripVertical className="w-3.5 h-3.5" />
        </div>

        {/* '⋮' Context Menu Button */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setShowMenu(!showMenu);
              setConfirmDelete(false);
            }}
            className="p-1 rounded text-slate-400 hover:text-slate-800 hover:bg-slate-100 transition"
            title="Block options"
            aria-label="Block options"
          >
            <MoreVertical className="w-3.5 h-3.5" />
          </button>

          {showMenu && (
            <div className="absolute left-0 top-full mt-1 w-44 bg-white border border-slate-200 rounded-xl shadow-xl py-1 z-50 text-xs animate-in fade-in zoom-in-95">
              <button
                type="button"
                onClick={() => {
                  moveTopLevelBlock(editor, 'up');
                  setShowMenu(false);
                }}
                disabled={activeNodeInfo.index === 0}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-slate-700 hover:bg-slate-50 disabled:opacity-30 disabled:hover:bg-transparent text-left"
              >
                <ArrowUp className="w-3.5 h-3.5" />
                <span>Move up (Alt+↑)</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  moveTopLevelBlock(editor, 'down');
                  setShowMenu(false);
                }}
                disabled={activeNodeInfo.index >= editor.state.doc.childCount - 1}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-slate-700 hover:bg-slate-50 disabled:opacity-30 disabled:hover:bg-transparent text-left"
              >
                <ArrowDown className="w-3.5 h-3.5" />
                <span>Move down (Alt+↓)</span>
              </button>

              <button
                type="button"
                onClick={handleDuplicate}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-slate-700 hover:bg-slate-50 text-left"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Duplicate block</span>
              </button>

              <div className="my-1 border-t border-slate-100" />

              {confirmDelete ? (
                <div className="px-3 py-1.5 bg-rose-50 border border-rose-200 rounded-md mx-1 space-y-1">
                  <div className="text-[11px] font-semibold text-rose-800 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3 text-rose-600" />
                    <span>Delete this block?</span>
                  </div>
                  <div className="flex gap-1 justify-end pt-0.5">
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(false)}
                      className="px-2 py-0.5 text-[11px] text-slate-600 hover:bg-white rounded"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleDelete}
                      className="px-2 py-0.5 text-[11px] bg-rose-600 text-white font-semibold rounded hover:bg-rose-700"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmDelete(true)}
                  className="w-full flex items-center gap-2 px-3 py-1.5 text-rose-600 hover:bg-rose-50 text-left font-medium"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Delete block</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
};
