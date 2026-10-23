import React, { useState } from 'react';
import { Sparkles, ShieldCheck, ChevronRight, ChevronLeft, X } from 'lucide-react';
import { EditorErrorBoundary } from './EditorErrorBoundary';
import { TemplateField } from './FieldsPanel';
import { DesignSettings } from './DesignPanel';
import { ChecksPanel } from './ChecksPanel';
import { EditorChatPanel } from '../assistant/EditorChatPanel';

// Fields and Design live in the left panel only, so the two sides never repeat each other
export type RightTabType = 'chat' | 'checks';

interface RightTabsPanelProps {
  clubId: string;
  templateId: string;
  editor: any;
  fields: TemplateField[];
  designSettings: DesignSettings;
  onApplyChatAction: (action: any, actionId?: string) => { ok: boolean; message?: string } | void;
  onUndoChatAction?: (actionId: string) => boolean;
  isOpen: boolean;
  onToggle: () => void;
  isMobile?: boolean;
  /** Controlled tab (e.g. the phone action bar opens AI help directly) */
  activeTab?: RightTabType;
  onTabChange?: (tab: RightTabType) => void;
}

export const RightTabsPanel: React.FC<RightTabsPanelProps> = ({
  clubId,
  templateId,
  editor,
  fields,
  designSettings,
  onApplyChatAction,
  onUndoChatAction,
  isOpen,
  onToggle,
  isMobile = false,
  activeTab: controlledTab,
  onTabChange,
}) => {
  const [ownTab, setOwnTab] = useState<RightTabType>('chat');
  const activeTab = controlledTab ?? ownTab;
  const setActiveTab = (tab: RightTabType) => (onTabChange ? onTabChange(tab) : setOwnTab(tab));

  if (!isOpen) {
    if (isMobile) return null;
    return (
      <aside className="border-l border-slate-200 bg-slate-50 flex flex-col items-center py-3 px-1 transition-all select-none">
        <button
          onClick={onToggle}
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200 transition"
          title="Expand Right Panel"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span
          className="text-[11px] font-bold text-slate-400 mt-6 select-none cursor-pointer flex items-center gap-1.5"
          style={{ writingMode: 'vertical-rl' }}
          onClick={onToggle}
        >
          <Sparkles className="w-3 h-3 text-brand-500" />
          AI & Tools Panel
        </span>
      </aside>
    );
  }

  // Mobile bottom sheet vs desktop sidebar
  const containerClasses = isMobile
    ? 'fixed inset-x-0 bottom-0 z-40 bg-white border-t border-slate-200 shadow-2xl h-[70vh] flex flex-col'
    : 'w-80 lg:w-96 border-l border-slate-200 bg-white flex flex-col h-[calc(100vh-53px)] transition-all select-none';

  return (
    <>
      {isMobile && (
        <div
          className="fixed inset-0 bg-slate-900/40 z-30 lg:hidden"
          onClick={onToggle}
          aria-hidden="true"
        />
      )}
      <aside className={containerClasses}>
      {/* Tab Navigation Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-2 py-1.5 bg-slate-50/80">
        <div className="flex items-center gap-1 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition ${
              activeTab === 'chat'
                ? 'bg-white text-brand-600 shadow-sm border border-slate-200/80'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI help</span>
          </button>

          <button
            onClick={() => setActiveTab('checks')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition ${
              activeTab === 'checks'
                ? 'bg-white text-brand-600 shadow-sm border border-slate-200/80'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Checks</span>
          </button>
        </div>

        <button
          onClick={onToggle}
          className="p-2 sm:p-1 min-w-[44px] min-h-[44px] sm:min-w-0 sm:min-h-0 flex items-center justify-center text-slate-400 hover:text-slate-600 rounded transition"
          title="Collapse Panel"
          aria-label="Collapse panel"
        >
          {isMobile ? <X className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {/* Tab Body with ErrorBoundary */}
      <div className="flex-1 overflow-hidden relative">
        {/* Kept mounted so the conversation and its Undo buttons survive tab switches */}
        <div className={activeTab === 'chat' ? 'h-full' : 'hidden'}>
          <EditorErrorBoundary title="AI Chat Copilot Error">
            <EditorChatPanel
              clubId={clubId}
              templateId={templateId}
              onApply={onApplyChatAction}
              onUndo={onUndoChatAction}
              selectedText={
                editor?.state?.selection && !editor.state.selection.empty
                  ? editor.state.doc.textBetween(editor.state.selection.from, editor.state.selection.to, ' ')
                  : undefined
              }
              documentContext={{
                title: editor?.state?.doc?.firstChild?.textContent || 'Document',
                fields: fields.map((f) => ({ key: f.key, label: f.label, type: f.type, required: f.required })),
                theme: designSettings.theme,
                selected_block_id: (() => {
                  const $from = editor?.state?.selection?.$from;
                  return $from && $from.depth > 0 ? $from.node(1)?.attrs?.blockId || undefined : undefined;
                })(),
                // Every top-level block with its full text, so suggestions can target the right one
                blocks: (() => {
                  const out: { type: string; blockId?: string; text: string }[] = [];
                  editor?.state?.doc?.forEach((n: any) => {
                    const kind = n.type.name === 'table' ? n.attrs.blockType || 'table' : n.type.name === 'heading' ? `heading${n.attrs.level}` : n.type.name;
                    out.push({ type: kind, blockId: n.attrs?.blockId, text: (n.textContent || n.attrs?.imageType || '').slice(0, 160) });
                  });
                  return out.slice(0, 40);
                })(),
              }}
              className="h-full border-none shadow-none"
            />
          </EditorErrorBoundary>
        </div>

        {activeTab === 'checks' && (
          <EditorErrorBoundary title="Checks Panel Error">
            <ChecksPanel
              editor={editor}
              fields={fields}
              clubId={clubId}
              templateId={templateId}
              theme={designSettings.theme}
              onApplyChatAction={onApplyChatAction}
            />
          </EditorErrorBoundary>
        )}
      </div>
    </aside>
    </>
  );
};
