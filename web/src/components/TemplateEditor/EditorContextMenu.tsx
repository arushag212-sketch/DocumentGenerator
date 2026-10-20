import React, { useEffect, useRef, useState } from 'react';
import type { Editor } from '@tiptap/core';
import {
  Scissors,
  Copy,
  ClipboardPaste,
  Bold,
  Italic,
  Underline as UnderlineIcon,
  AlignLeft,
  AlignCenter,
  AlignRight,
  CopyPlus,
  Trash2,
} from 'lucide-react';
import { FontControls } from './FontControls';

type MenuState = { x: number; y: number } | null;

/** The top-level block holding the cursor (for duplicate / delete). */
function topBlock(editor: Editor): { pos: number; size: number; json: any } | null {
  const { $from } = editor.state.selection;
  if ($from.depth < 1) return null;
  const node = $from.node(1);
  return { pos: $from.before(1), size: node.nodeSize, json: node.toJSON() };
}

/**
 * Right-click menu for the template canvas, replacing the browser's own menu with the actions
 * that make sense in a document template.
 */
export const EditorContextMenu: React.FC<{ editor: Editor | null; containerRef: React.RefObject<HTMLElement> }> = ({
  editor,
  containerRef,
}) => {
  const [menu, setMenu] = useState<MenuState>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !editor) return;
    const onContextMenu = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.ProseMirror')) return;
      e.preventDefault();
      // Right-clicking outside the current selection moves the cursor there, like a word processor
      const { from, to } = editor.state.selection;
      const at = editor.view.posAtCoords({ left: e.clientX, top: e.clientY });
      if (at && (at.pos < from || at.pos > to)) editor.chain().focus().setTextSelection(at.pos).run();
      else editor.commands.focus();
      const width = 236;
      const height = 320;
      setNotice(null);
      setMenu({
        x: Math.min(e.clientX, window.innerWidth - width - 8),
        y: Math.min(e.clientY, window.innerHeight - height - 8),
      });
    };
    el.addEventListener('contextmenu', onContextMenu);
    return () => el.removeEventListener('contextmenu', onContextMenu);
  }, [editor, containerRef]);

  useEffect(() => {
    if (!menu) return;
    const close = (e: Event) => {
      if (e instanceof MouseEvent && menuRef.current?.contains(e.target as Node)) return;
      setMenu(null);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenu(null);
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', close);
    containerRef.current?.addEventListener('scroll', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', close);
      containerRef.current?.removeEventListener('scroll', close);
    };
  }, [menu, containerRef]);

  if (!menu || !editor) return null;

  const hasSelection = !editor.state.selection.empty;
  const run = (fn: () => void) => () => {
    fn();
    setMenu(null);
  };
  const clipboard = (command: 'cut' | 'copy') => {
    editor.commands.focus();
    const ok = document.execCommand(command);
    if (!ok) setNotice(`Use Ctrl+${command === 'cut' ? 'X' : 'C'} to ${command}.`);
    else setMenu(null);
  };
  const paste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) editor.chain().focus().insertContent(text).run();
      setMenu(null);
    } catch {
      setNotice('Use Ctrl+V to paste (the browser blocked clipboard access).');
    }
  };

  const item = 'w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-left text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-transparent';
  const kbd = 'ml-auto text-[11px] text-slate-400';

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label="Editor actions"
      style={{ top: menu.y, left: menu.x }}
      className="fixed z-[60] w-[236px] rounded-lg border border-slate-200 bg-white p-1 shadow-xl"
      onContextMenu={(e) => e.preventDefault()}
    >
      <button role="menuitem" className={item} disabled={!hasSelection} onClick={() => clipboard('cut')}>
        <Scissors className="w-3.5 h-3.5" /> Cut <span className={kbd}>Ctrl+X</span>
      </button>
      <button role="menuitem" className={item} disabled={!hasSelection} onClick={() => clipboard('copy')}>
        <Copy className="w-3.5 h-3.5" /> Copy <span className={kbd}>Ctrl+C</span>
      </button>
      <button role="menuitem" className={item} onClick={paste}>
        <ClipboardPaste className="w-3.5 h-3.5" /> Paste <span className={kbd}>Ctrl+V</span>
      </button>

      <div className="my-1 h-px bg-slate-100" />
      <div className="flex gap-0.5 px-1">
        {[
          { label: 'Bold', icon: Bold, on: () => editor.chain().focus().toggleBold().run(), active: editor.isActive('bold') },
          { label: 'Italic', icon: Italic, on: () => editor.chain().focus().toggleItalic().run(), active: editor.isActive('italic') },
          { label: 'Underline', icon: UnderlineIcon, on: () => editor.chain().focus().toggleUnderline().run(), active: editor.isActive('underline') },
          { label: 'Align left', icon: AlignLeft, on: () => editor.chain().focus().setTextAlign('left').run(), active: editor.isActive({ textAlign: 'left' }) },
          { label: 'Align centre', icon: AlignCenter, on: () => editor.chain().focus().setTextAlign('center').run(), active: editor.isActive({ textAlign: 'center' }) },
          { label: 'Align right', icon: AlignRight, on: () => editor.chain().focus().setTextAlign('right').run(), active: editor.isActive({ textAlign: 'right' }) },
        ].map(({ label, icon: Icon, on, active }) => (
          <button
            key={label}
            role="menuitem"
            title={label}
            aria-label={label}
            onClick={run(on)}
            className={`p-1.5 rounded-md hover:bg-slate-100 ${active ? 'bg-slate-100 text-brand-700' : 'text-slate-600'}`}
          >
            <Icon className="w-3.5 h-3.5" />
          </button>
        ))}
      </div>

      <div className="my-1 h-px bg-slate-100" />
      <FontControls variant="menu" editor={editor} onApplied={() => setMenu(null)} />

      <div className="my-1 h-px bg-slate-100" />
      <button
        role="menuitem"
        className={item}
        onClick={run(() => {
          const b = topBlock(editor);
          if (!b) return;
          const copy = { ...b.json, attrs: { ...(b.json.attrs || {}) } };
          delete copy.attrs.blockId;
          editor.chain().focus().insertContentAt(b.pos + b.size, copy).run();
        })}
      >
        <CopyPlus className="w-3.5 h-3.5" /> Duplicate block
      </button>
      <button
        role="menuitem"
        className={`${item} text-red-600 hover:bg-red-50`}
        onClick={run(() => {
          const b = topBlock(editor);
          if (b) editor.chain().focus().deleteRange({ from: b.pos, to: b.pos + b.size }).run();
        })}
      >
        <Trash2 className="w-3.5 h-3.5" /> Delete block
      </button>

      {notice && <p className="px-2.5 pt-1 pb-0.5 text-[11px] text-slate-500">{notice}</p>}
    </div>
  );
};
