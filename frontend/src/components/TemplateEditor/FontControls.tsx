import React, { useState, useEffect } from 'react';
import type { Editor } from '@tiptap/core';
import { ChevronDown } from 'lucide-react';
import { FONT_OPTIONS } from './themes';
import { FONT_SIZES, applyBlockStyle, currentBlockStyle } from './blockStyle';

export interface FontControlsProps {
  editor: Editor | null;
  variant: 'toolbar' | 'menu' | 'bubble';
  onApplied?: () => void;
  className?: string;
}

export const FontControls: React.FC<FontControlsProps> = ({
  editor,
  variant,
  onApplied,
  className = '',
}) => {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!editor) return;
    const update = () => setTick((t) => t + 1);
    editor.on('transaction', update);
    editor.on('selectionUpdate', update);
    return () => {
      editor.off('transaction', update);
      editor.off('selectionUpdate', update);
    };
  }, [editor]);

  const blockStyle = editor ? currentBlockStyle(editor) : { fontFamily: '', fontSize: '' };

  const fontId =
    variant === 'toolbar' ? 'toolbar-font' : variant === 'menu' ? 'ctx-font' : 'bubble-font';
  const sizeId =
    variant === 'toolbar' ? 'toolbar-size' : variant === 'menu' ? 'ctx-size' : 'bubble-size';

  const selectedFont = FONT_OPTIONS.find((f) => f.id === blockStyle.fontFamily);
  const fontTitle = selectedFont ? selectedFont.name : blockStyle.fontFamily || 'Default font';
  const sizeTitle = blockStyle.fontSize ? `${blockStyle.fontSize} pt` : 'Font size (pt)';

  const isCustomFont =
    Boolean(blockStyle.fontFamily && !FONT_OPTIONS.some((f) => f.id === blockStyle.fontFamily));
  const isCustomSize =
    Boolean(blockStyle.fontSize && !FONT_SIZES.includes(blockStyle.fontSize));

  const handleFontChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (editor) {
      applyBlockStyle(editor, { fontFamily: e.target.value || null });
    }
    onApplied?.();
  };

  const handleSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (editor) {
      applyBlockStyle(editor, { fontSize: e.target.value ? `${e.target.value}pt` : null });
    }
    onApplied?.();
  };

  const isBubble = variant === 'bubble';
  const isMenu = variant === 'menu';
  const isToolbar = variant === 'toolbar';

  // Base styling for selects
  const baseSelectClasses =
    'appearance-none rounded-md font-medium cursor-pointer outline-none transition-colors ' +
    'focus:outline-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:border-transparent ';

  const themeClasses = isBubble
    ? 'bg-slate-800 text-slate-100 border border-slate-700 hover:border-slate-600 '
    : 'bg-white text-slate-700 border border-slate-200 hover:border-slate-300 ';

  const heightClass = isBubble ? 'h-6 text-xs' : 'h-7 text-xs';

  const containerClasses = isMenu
    ? `flex items-center gap-2 px-1 pb-1 w-full ${className}`
    : `flex items-center gap-1 ${className}`;

  const fontWrapperClasses = isMenu
    ? 'relative flex-1 min-w-0 flex items-center'
    : isToolbar
    ? 'relative flex items-center min-w-[110px] sm:min-w-[128px] max-w-[160px] flex-shrink'
    : 'relative flex items-center w-[128px] min-w-[110px] max-w-[140px] shrink-0';

  const sizeWrapperClasses = 'relative w-[68px] shrink-0 flex items-center';

  const fontSelectClasses = `${heightClass} ${baseSelectClasses} ${themeClasses} w-full pl-2 pr-6 truncate`;
  const sizeSelectClasses = `${heightClass} ${baseSelectClasses} ${themeClasses} w-full pl-2 pr-5 tabular-nums`;

  const chevronClass = isBubble
    ? 'w-3 h-3 absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400'
    : 'w-3.5 h-3.5 absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400';

  const optionClass = isBubble ? 'bg-slate-900 text-white' : undefined;

  return (
    <div className={containerClasses}>
      {/* Font Family Control */}
      <div className={fontWrapperClasses}>
        <label className="sr-only" htmlFor={fontId}>
          Font family
        </label>
        <select
          id={fontId}
          title={fontTitle}
          value={blockStyle.fontFamily}
          onMouseDown={(e) => e.stopPropagation()}
          onChange={handleFontChange}
          style={{ outline: 'none' }}
          className={fontSelectClasses}
        >
          <option value="" className={optionClass}>
            Default font
          </option>
          {isCustomFont && (
            <option
              value={blockStyle.fontFamily}
              style={{ fontFamily: blockStyle.fontFamily }}
              className={optionClass}
            >
              {blockStyle.fontFamily}
            </option>
          )}
          {FONT_OPTIONS.map((f) => (
            <option
              key={f.id}
              value={f.id}
              style={{ fontFamily: f.family }}
              className={optionClass}
            >
              {f.name}
            </option>
          ))}
        </select>
        <ChevronDown className={chevronClass} aria-hidden="true" />
      </div>

      {/* Font Size Control */}
      <div className={sizeWrapperClasses}>
        <label className="sr-only" htmlFor={sizeId}>
          Font size (pt)
        </label>
        <select
          id={sizeId}
          title={sizeTitle}
          value={blockStyle.fontSize}
          onMouseDown={(e) => e.stopPropagation()}
          onChange={handleSizeChange}
          style={{ outline: 'none' }}
          className={sizeSelectClasses}
        >
          <option value="" className={optionClass}>
            Size
          </option>
          {isCustomSize && (
            <option value={blockStyle.fontSize} className={optionClass}>
              {blockStyle.fontSize} pt
            </option>
          )}
          {FONT_SIZES.map((sz) => (
            <option key={sz} value={sz} className={optionClass}>
              {sz} pt
            </option>
          ))}
        </select>
        <ChevronDown className={chevronClass} aria-hidden="true" />
      </div>
    </div>
  );
};
