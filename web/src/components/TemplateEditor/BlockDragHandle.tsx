import React, { useState, useEffect } from 'react';
import { NodeSelection } from '@tiptap/pm/state';
import {
  GripVertical,
  ArrowUp,
  ArrowDown,
  Copy,
  Trash2,
  Lock,
} from 'lucide-react';
import { isLockedNode, moveTopLevelBlock } from './blockDragDrop';

interface BlockDragHandleProps {
  editor: any;
  containerRef: React.RefObject<HTMLDivElement>;
}

export const BlockDragHandle: React.FC<BlockDragHandleProps> = ({ editor, containerRef }) => {
  const [handlePos, setHandlePos] = useState<{ top: number; left: number } | null>(null);
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
        left: Math.max(10, rect.left - containerRect.left - 52),
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
  };

  const handleDelete = () => {
    if (!editor || activeNodeInfo.isLocked) return;
    const { state, view } = editor;
    const node = state.doc.child(activeNodeInfo.index);
    view.dispatch(state.tr.delete(activeNodeInfo.pos, activeNodeInfo.pos + node.nodeSize));
  };

  if (activeNodeInfo.isLocked) {
    return (
      <div
        style={{ top: `${handlePos.top}px`, left: `${handlePos.left}px` }}
        className="absolute z-30 flex items-center gap-1 bg-amber-50 border border-amber-300 text-amber-800 text-[11px] font-bold px-2 py-1 rounded-md shadow-sm select-none"
        title="SVNIT Letterhead Slot (Locked, cannot be moved or deleted)"
      >
        <Lock className="w-3 h-3 text-amber-600" />
        <span>Locked</span>
      </div>
    );
  }

  return (
    <div
      style={{ top: `${handlePos.top}px`, left: `${handlePos.left}px` }}
      className="absolute z-30 flex items-center gap-0.5 bg-white/95 backdrop-blur border border-slate-200 rounded-lg shadow-md px-1 py-0.5 select-none transition-all group"
    >
      {/* Drag handle grip */}
      <div
        draggable
        onDragStart={handleDragStart}
        className="p-1 rounded cursor-grab active:cursor-grabbing text-slate-400 hover:text-brand-600 hover:bg-brand-50 transition"
        title="Drag block to reorder"
      >
        <GripVertical className="w-3.5 h-3.5" />
      </div>

      {/* Move Up */}
      <button
        onClick={() => moveTopLevelBlock(editor, 'up')}
        disabled={activeNodeInfo.index === 0}
        className="p-1 rounded text-slate-400 hover:text-slate-800 hover:bg-slate-100 disabled:opacity-30 disabled:hover:bg-transparent transition"
        title="Move block up (Alt+Up)"
      >
        <ArrowUp className="w-3 h-3" />
      </button>

      {/* Move Down */}
      <button
        onClick={() => moveTopLevelBlock(editor, 'down')}
        disabled={activeNodeInfo.index >= editor.state.doc.childCount - 1}
        className="p-1 rounded text-slate-400 hover:text-slate-800 hover:bg-slate-100 disabled:opacity-30 disabled:hover:bg-transparent transition"
        title="Move block down (Alt+Down)"
      >
        <ArrowDown className="w-3 h-3" />
      </button>

      <div className="w-px h-3 bg-slate-200 mx-0.5" />

      {/* Duplicate */}
      <button
        onClick={handleDuplicate}
        className="p-1 rounded text-slate-400 hover:text-slate-800 hover:bg-slate-100 transition"
        title="Duplicate block"
      >
        <Copy className="w-3 h-3" />
      </button>

      {/* Delete */}
      <button
        onClick={handleDelete}
        className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition"
        title="Delete block"
      >
        <Trash2 className="w-3 h-3" />
      </button>
    </div>
  );
};
