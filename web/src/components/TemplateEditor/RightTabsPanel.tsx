import React, { useState } from 'react';
import { Sparkles, Tag, Palette, ShieldCheck, ChevronRight, ChevronLeft, X } from 'lucide-react';
import { EditorErrorBoundary } from './EditorErrorBoundary';
import { FieldsPanel, TemplateField } from './FieldsPanel';
import { DesignPanel, DesignSettings } from './DesignPanel';
import { ChecksPanel } from './ChecksPanel';
import { EditorChatPanel } from '../EditorChatPanel';

export type RightTabType = 'chat' | 'fields' | 'design' | 'checks';

interface RightTabsPanelProps {
  clubId: string;
  templateId: string;
  editor: any;
  fields: TemplateField[];
  onAddField: (field: TemplateField) => void;
  designSettings: DesignSettings;
  onDesignChange: (settings: Partial<DesignSettings>) => void;
  onAutoStyle?: () => void;
  onApplyChatAction: (action: any) => void;
  isOpen: boolean;
  onToggle: () => void;
  isMobile?: boolean;
}

export const RightTabsPanel: React.FC<RightTabsPanelProps> = ({
  clubId,
  templateId,
  editor,
  fields,
  onAddField,
  designSettings,
  onDesignChange,
  onAutoStyle,
  onApplyChatAction,
  isOpen,
  onToggle,
  isMobile = false,
}) => {
  const [activeTab, setActiveTab] = useState<RightTabType>('chat');

  if (!isOpen && !isMobile) {
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
          className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-6 select-none cursor-pointer flex items-center gap-1.5"
          style={{ writingMode: 'vertical-rl' }}
          onClick={onToggle}
        >
          <Sparkles className="w-3 h-3 text-indigo-500" />
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
    <aside className={containerClasses}>
      {/* Tab Navigation Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-2 py-1.5 bg-slate-50/80">
        <div className="flex items-center gap-1 text-[11px] font-semibold">
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition ${
              activeTab === 'chat'
                ? 'bg-white text-indigo-600 shadow-sm border border-slate-200/80'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Chat</span>
          </button>

          <button
            onClick={() => setActiveTab('fields')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition ${
              activeTab === 'fields'
                ? 'bg-white text-indigo-600 shadow-sm border border-slate-200/80'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Tag className="w-3.5 h-3.5" />
            <span>Fields</span>
          </button>

          <button
            onClick={() => setActiveTab('design')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition ${
              activeTab === 'design'
                ? 'bg-white text-indigo-600 shadow-sm border border-slate-200/80'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Palette className="w-3.5 h-3.5" />
            <span>Design</span>
          </button>

          <button
            onClick={() => setActiveTab('checks')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition ${
              activeTab === 'checks'
                ? 'bg-white text-indigo-600 shadow-sm border border-slate-200/80'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Checks</span>
          </button>
        </div>

        <button
          onClick={onToggle}
          className="p-1 text-slate-400 hover:text-slate-600 rounded transition"
          title="Collapse Panel"
        >
          {isMobile ? <X className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {/* Tab Body with ErrorBoundary */}
      <div className="flex-1 overflow-hidden relative">
        {activeTab === 'chat' && (
          <EditorErrorBoundary title="AI Chat Copilot Error">
            <EditorChatPanel
              clubId={clubId}
              templateId={templateId}
              onApply={onApplyChatAction}
              onUndo={() => editor?.commands?.undo()}
              selectedText={
                editor?.state?.selection && !editor.state.selection.empty
                  ? editor.state.doc.textBetween(editor.state.selection.from, editor.state.selection.to, ' ')
                  : undefined
              }
              documentContext={{
                title: editor?.state?.doc?.firstChild?.textContent || 'Document',
                fields: fields.map((f) => ({ key: f.key, label: f.label, type: f.type, required: f.required })),
                theme: designSettings.theme,
                blocks: (editor?.getJSON()?.content || []).slice(0, 30).map((b: any) => ({
                  type: b.type,
                  blockId: b.attrs?.blockId,
                  text: b.content?.[0]?.text?.slice(0, 80) || '',
                })),
              }}
              className="h-full border-none shadow-none"
            />
          </EditorErrorBoundary>
        )}

        {activeTab === 'fields' && (
          <EditorErrorBoundary title="Fields Panel Error">
            <FieldsPanel fields={fields} onAddField={onAddField} editor={editor} />
          </EditorErrorBoundary>
        )}

        {activeTab === 'design' && (
          <EditorErrorBoundary title="Design Panel Error">
            <DesignPanel
              settings={designSettings}
              onChange={onDesignChange}
              onAutoStyle={onAutoStyle}
            />
          </EditorErrorBoundary>
        )}

        {activeTab === 'checks' && (
          <EditorErrorBoundary title="Checks Panel Error">
            <ChecksPanel editor={editor} fields={fields} />
          </EditorErrorBoundary>
        )}
      </div>
    </aside>
  );
};
