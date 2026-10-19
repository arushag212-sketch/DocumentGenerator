import React, { useCallback, useMemo, useState } from 'react';
import { AlertCircle, Check, LoaderCircle, RotateCcw, Send, Sparkles, X } from 'lucide-react';
import { actionPreview, requestEditorAssistant } from './editorAssistant';
import type {
  EditorAssistantAction,
  EditorAssistantDocumentContext,
  EditorAssistantFetcher,
  EditorAssistantRequest,
} from './editorAssistant';

export type {
  EditorAssistantAction,
  EditorAssistantDocumentContext,
  EditorAssistantFetcher,
  EditorAssistantRequest,
} from './editorAssistant';

export type EditorChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  actions?: EditorAssistantAction[];
  source?: 'gemini' | 'local';
  warnings?: string[];
};

export type EditorChatPanelProps = {
  clubId: string;
  templateId?: string;
  documentContext?: EditorAssistantDocumentContext;
  selectedText?: string;
  onApply: (action: EditorAssistantAction) => void;
  requestAssistant?: EditorAssistantFetcher;
  onClose?: () => void;
  className?: string;
  disabled?: boolean;
  placeholder?: string;
};

const STARTER_PROMPTS = [
  'Set the title to Event Permission Letter',
  'Add a required event date field',
  'Insert a signature block',
  'Rewrite the selected text professionally',
];

function messageId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Reusable right-side assistant panel for document editors.
 *
 * It never mutates an editor directly.  Every model/local suggestion is
 * surfaced as a typed action and handed to `onApply`, allowing the host editor
 * to decide whether to update state, insert TipTap content, resolve a logo, or
 * save a draft.
 */
export const EditorChatPanel: React.FC<EditorChatPanelProps> = ({
  clubId,
  templateId,
  documentContext,
  selectedText,
  onApply,
  requestAssistant,
  onClose,
  className = '',
  disabled = false,
  placeholder = 'Tell me what to change in this document…',
}) => {
  const [messages, setMessages] = useState<EditorChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRequest, setLastRequest] = useState<EditorAssistantRequest | null>(null);
  const [appliedActions, setAppliedActions] = useState<Set<string>>(new Set());

  const fetchAssistant = useMemo<EditorAssistantFetcher>(
    () =>
      requestAssistant || ((request: EditorAssistantRequest) => requestEditorAssistant(clubId, templateId, request)),
    [clubId, requestAssistant, templateId]
  );

  const submitRequest = useCallback(
    async (request: EditorAssistantRequest, addUserMessage = true) => {
      const instruction = request.instruction.trim();
      if (!instruction || loading || disabled) return;

      const normalizedRequest: EditorAssistantRequest = {
        ...request,
        instruction,
        selectedText: request.selectedText ?? selectedText,
        documentContext: request.documentContext ?? documentContext,
      };
      setError(null);
      setLastRequest(normalizedRequest);
      if (addUserMessage) {
        setMessages(previous => [
          ...previous,
          { id: messageId('user'), role: 'user', content: instruction },
        ]);
      }
      setLoading(true);
      try {
        const result = await fetchAssistant(normalizedRequest);
        setMessages(previous => [
          ...previous,
          {
            id: messageId('assistant'),
            role: 'assistant',
            content: result.message,
            actions: result.actions,
            source: result.source,
            warnings: result.warnings,
          },
        ]);
        setDraft('');
      } catch (requestError) {
        const message = requestError instanceof Error ? requestError.message : 'The assistant could not process that request.';
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [disabled, documentContext, fetchAssistant, loading, selectedText]
  );

  const sendMessage = useCallback(() => {
    void submitRequest({ instruction: draft });
  }, [draft, submitRequest]);

  const applyAction = useCallback(
    (messageIdValue: string, actionIndex: number, action: EditorAssistantAction) => {
      const actionId = `${messageIdValue}:${actionIndex}`;
      if (appliedActions.has(actionId)) return;
      onApply(action);
      setAppliedActions(previous => {
        const next = new Set(previous);
        next.add(actionId);
        return next;
      });
    },
    [appliedActions, onApply]
  );

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      sendMessage();
    }
  };

  return (
    <aside
      className={`flex h-full min-h-[520px] w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-xl ${className}`}
      aria-label="Document assistant"
    >
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Document assistant</h2>
            <p className="text-[11px] text-slate-500">Describe a change in plain language</p>
          </div>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-slate-400 transition hover:bg-white hover:text-slate-700"
            aria-label="Close document assistant"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite">
        {messages.length === 0 && !loading && (
          <div className="rounded-xl border border-dashed border-indigo-200 bg-indigo-50/60 p-4">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-indigo-950">
              <Sparkles className="h-4 w-4 text-indigo-600" aria-hidden="true" />
              Start with a simple instruction
            </div>
            <p className="mb-3 text-xs leading-relaxed text-indigo-900/70">
              I’ll prepare reviewable edits for the title, fields, blocks, logo, or selected text.
            </p>
            <div className="flex flex-wrap gap-2">
              {STARTER_PROMPTS.map(prompt => (
                <button
                  key={prompt}
                  type="button"
                  disabled={disabled}
                  onClick={() => setDraft(prompt)}
                  className="rounded-full border border-indigo-200 bg-white px-2.5 py-1 text-left text-[11px] font-medium text-indigo-800 transition hover:border-indigo-400 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(message => (
          <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[92%] rounded-2xl px-3 py-2.5 text-sm shadow-sm ${
                message.role === 'user'
                  ? 'rounded-br-sm bg-indigo-600 text-white'
                  : 'rounded-bl-sm border border-slate-200 bg-slate-50 text-slate-800'
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
              {message.role === 'assistant' && message.source === 'local' && (
                <span className="mt-2 inline-flex rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                  Local suggestions
                </span>
              )}
              {message.warnings && message.warnings.length > 0 && (
                <div className="mt-2 space-y-1 text-[11px] text-amber-800">
                  {message.warnings.map((warning, index) => (
                    <p key={`${message.id}-warning-${index}`} className="flex gap-1.5">
                      <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                      <span>{warning}</span>
                    </p>
                  ))}
                </div>
              )}
              {message.actions && message.actions.length > 0 && (
                <div className="mt-3 space-y-2 border-t border-slate-200 pt-2">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Suggested edits</p>
                  {message.actions.map((action, actionIndex) => {
                    const actionId = `${message.id}:${actionIndex}`;
                    const applied = appliedActions.has(actionId);
                    return (
                      <div key={actionId} className="rounded-lg border border-slate-200 bg-white p-2">
                        <p className="text-xs font-semibold text-slate-800">{action.summary}</p>
                        <p className="mt-0.5 line-clamp-3 text-[11px] text-slate-500">{actionPreview(action)}</p>
                        <button
                          type="button"
                          disabled={applied || disabled}
                          onClick={() => applyAction(message.id, actionIndex, action)}
                          className={`mt-2 inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-semibold transition ${
                            applied
                              ? 'cursor-default bg-emerald-50 text-emerald-700'
                              : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
                          }`}
                        >
                          {applied ? <Check className="h-3 w-3" aria-hidden="true" /> : null}
                          {applied ? 'Applied' : 'Apply suggestion'}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-2xl rounded-bl-sm border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-500">
              <LoaderCircle className="h-4 w-4 animate-spin text-indigo-600" aria-hidden="true" />
              Preparing suggestions…
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800" role="alert">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="font-semibold">The assistant couldn’t respond.</p>
                <p className="mt-0.5 break-words text-rose-700/80">{error}</p>
                {lastRequest && (
                  <button
                    type="button"
                    onClick={() => void submitRequest(lastRequest, false)}
                    disabled={loading || disabled}
                    className="mt-2 inline-flex items-center gap-1 rounded-md bg-white px-2 py-1 font-semibold text-rose-700 shadow-sm hover:bg-rose-100 disabled:opacity-50"
                  >
                    <RotateCcw className="h-3 w-3" aria-hidden="true" />
                    Try again
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 bg-white p-3">
        {selectedText && (
          <p className="mb-2 truncate rounded-md bg-slate-50 px-2 py-1 text-[10px] text-slate-500" title={selectedText}>
            Selected text: “{selectedText}”
          </p>
        )}
        <div className="rounded-xl border border-slate-300 bg-white shadow-sm focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100">
          <textarea
            value={draft}
            onChange={event => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled || loading}
            placeholder={placeholder}
            rows={3}
            maxLength={4000}
            className="w-full resize-none rounded-xl border-0 bg-transparent px-3 py-2 text-sm text-slate-800 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
            aria-label="Assistant instruction"
          />
          <div className="flex items-center justify-between px-2 pb-2">
            <span className="text-[10px] text-slate-400">Ctrl/⌘ + Enter to send</span>
            <button
              type="button"
              onClick={sendMessage}
              disabled={disabled || loading || !draft.trim()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
            >
              {loading ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <Send className="h-3.5 w-3.5" aria-hidden="true" />}
              Send
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default EditorChatPanel;
