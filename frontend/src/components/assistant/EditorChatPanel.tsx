import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  LoaderCircle,
  Mic,
  MicOff,
  RotateCcw,
  Send,
  Sparkles,
  X,
} from 'lucide-react';
import { requestEditorAssistant } from './editorAssistant';
import { EditorActionItem } from './EditorActionItem';
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
  /** Apply a suggestion; a result with ok=false keeps it un-applied and shows the reason. */
  onApply: (action: EditorAssistantAction, actionId?: string) => { ok: boolean; message?: string } | void;
  /** Restore the template to before this suggestion; returns false when it cannot. */
  onUndo?: (actionId: string) => boolean;
  requestAssistant?: EditorAssistantFetcher;
  onClose?: () => void;
  className?: string;
  disabled?: boolean;
  placeholder?: string;
};

const QUICK_ACTION_CHIPS = [
  'Make this a formal letter',
  'Add a table for expenses',
  'Change the theme to blue',
  'Add signature box',
];

function messageId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export const EditorChatPanel: React.FC<EditorChatPanelProps> = ({
  clubId,
  templateId,
  documentContext,
  selectedText,
  onApply,
  onUndo,
  requestAssistant,
  onClose,
  className = '',
  disabled = false,
  placeholder = 'Describe a change or ask a question…',
}) => {
  const [messages, setMessages] = useState<EditorChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRequest, setLastRequest] = useState<EditorAssistantRequest | null>(null);
  const [appliedActions, setAppliedActions] = useState<Set<string>>(new Set());
  const appliedOrderRef = useRef<string[]>([]);
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({});
  const [rejectedActions, setRejectedActions] = useState<Set<string>>(new Set());
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  const fetchAssistant = useMemo<EditorAssistantFetcher>(
    () =>
      requestAssistant || ((req: EditorAssistantRequest) => requestEditorAssistant(clubId, templateId, req)),
    [clubId, requestAssistant, templateId]
  );

  useEffect(() => {
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRec) {
      const rec = new SpeechRec();
      rec.continuous = false;
      rec.interimResults = false;
      rec.onresult = (e: any) => {
        const text = e.results[0][0].transcript;
        if (text) setDraft((prev) => (prev ? `${prev} ${text}` : text));
        setIsListening(false);
      };
      rec.onerror = () => setIsListening(false);
      rec.onend = () => setIsListening(false);
      recognitionRef.current = rec;
    }
  }, []);

  const toggleListening = () => {
    if (!recognitionRef.current) return;
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      setIsListening(true);
      recognitionRef.current.start();
    }
  };

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
        setMessages((prev) => [...prev, { id: messageId('user'), role: 'user', content: instruction }]);
      }
      setLoading(true);
      try {
        const result = await fetchAssistant(normalizedRequest);
        setMessages((prev) => [
          ...prev,
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
      } catch (err: any) {
        setError(err instanceof Error ? err.message : 'The assistant could not process that request.');
      } finally {
        setLoading(false);
      }
    },
    [disabled, documentContext, fetchAssistant, loading, selectedText]
  );

  const sendMessage = useCallback(() => {
    void submitRequest({ instruction: draft });
  }, [draft, submitRequest]);

  const applyAction = (msgId: string, idx: number, action: EditorAssistantAction) => {
    const actionId = `${msgId}:${idx}`;
    if (appliedActions.has(actionId)) return;
    const result = onApply(action, actionId);
    if (result && result.ok === false) {
      setActionErrors((prev) => ({ ...prev, [actionId]: result.message || 'This suggestion could not be applied.' }));
      return;
    }
    setActionErrors((prev) => {
      const next = { ...prev };
      delete next[actionId];
      return next;
    });
    appliedOrderRef.current.push(actionId);
    setAppliedActions((prev) => new Set(prev).add(actionId));
  };

  // Undo restores the template to before this suggestion, so suggestions applied after
  // it are undone too.
  const undoAction = (actionId: string) => {
    if (!onUndo || !onUndo(actionId)) return;
    const order = appliedOrderRef.current;
    const at = order.indexOf(actionId);
    const undone = at >= 0 ? order.slice(at) : [actionId];
    appliedOrderRef.current = at >= 0 ? order.slice(0, at) : order;
    setAppliedActions((prev) => {
      const next = new Set(prev);
      undone.forEach((id) => next.delete(id));
      return next;
    });
  };

  const rejectAction = (msgId: string, idx: number) => {
    const actionId = `${msgId}:${idx}`;
    setRejectedActions((prev) => new Set(prev).add(actionId));
  };

  return (
    <aside className={`flex h-full w-full flex-col bg-white ${className}`} aria-label="AI help">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/80 px-3 py-2">
        <div className="flex items-center gap-1.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-brand-100 text-brand-700">
            <Sparkles className="h-3.5 w-3.5" />
          </span>
          <div>
            <h2 className="text-xs font-bold text-slate-900">AI help</h2>
            <p className="text-xs text-slate-500">Describe a change in plain words and AI makes it</p>
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-white hover:text-slate-700" title="Close">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-3 text-xs" aria-live="polite">
        {messages.length === 0 && !loading && (
          <div className="rounded-xl border border-dashed border-brand-200 bg-brand-50/50 p-3">
            <div className="mb-1 flex items-center gap-1.5 font-semibold text-brand-900 text-xs">
              <Sparkles className="h-3.5 w-3.5 text-brand-600" />
              What would you like to edit?
            </div>
            <p className="mb-2 text-xs leading-relaxed text-brand-900/70">
              Ask to add fields, format tables, translate text, insert signatures, or apply styling.
            </p>
            <div className="flex flex-wrap gap-1.5">
              {QUICK_ACTION_CHIPS.map((chip) => (
                <button
                  key={chip}
                  disabled={disabled}
                  onClick={() => submitRequest({ instruction: chip })}
                  className="rounded-full border border-brand-200 bg-white px-2 py-0.5 text-xs font-medium text-brand-700 transition hover:bg-brand-100 disabled:opacity-50"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[92%] rounded-xl px-3 py-2 text-xs shadow-sm ${
                message.role === 'user'
                  ? 'rounded-br-sm bg-brand-600 text-white'
                  : 'rounded-bl-sm border border-slate-200 bg-slate-50 text-slate-800'
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>

              {message.warnings && message.warnings.length > 0 && (
                <div className="mt-1.5 space-y-1 text-xs text-amber-800 border-t border-amber-200/50 pt-1">
                  {message.warnings.map((w, i) => (
                    <p key={i} className="flex gap-1">
                      <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                      <span>{w}</span>
                    </p>
                  ))}
                </div>
              )}

              {message.actions && message.actions.length > 0 && (
                <div className="mt-2 space-y-1.5 border-t border-slate-200 pt-1.5">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-500">
                    <span>Proposed edits</span>
                    <span className="rounded bg-brand-50 px-1 py-0.2 text-xs text-brand-700 font-semibold lowercase">
                      AI-suggested
                    </span>
                  </div>

                  {message.actions.map((action, idx) => {
                    const actionId = `${message.id}:${idx}`;
                    return (
                      <EditorActionItem
                        key={actionId}
                        action={action}
                        actionId={actionId}
                        applied={appliedActions.has(actionId)}
                        rejected={rejectedActions.has(actionId)}
                        disabled={disabled}
                        onApply={() => applyAction(message.id, idx, action)}
                        onReject={() => rejectAction(message.id, idx)}
                        onUndo={onUndo ? () => undoAction(actionId) : undefined}
                        error={actionErrors[actionId]}
                        onClarifySelect={(opt) => submitRequest({ instruction: opt })}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 rounded-xl rounded-bl-sm border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
            <LoaderCircle className="h-3.5 w-3.5 animate-spin text-brand-600" />
            Preparing suggestions…
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-800">
            <div className="flex items-start gap-1.5">
              <AlertCircle className="h-3.5 w-3.5 text-rose-600 shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-xs">Assistant request failed</p>
                <p className="mt-0.5 text-xs text-rose-700">{error}</p>
                {lastRequest && (
                  <button
                    onClick={() => void submitRequest(lastRequest, false)}
                    className="mt-1.5 inline-flex items-center gap-1 rounded bg-white px-2 py-0.5 text-xs font-semibold text-rose-700 shadow-sm hover:bg-rose-100"
                  >
                    <RotateCcw className="h-2.5 w-2.5" /> Retry
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 bg-white p-2.5">
        {selectedText && (
          <div className="mb-1.5 flex items-center justify-between rounded bg-slate-50 px-2 py-1 text-xs text-slate-600">
            <span className="truncate max-w-[200px]">Selected: “{selectedText}”</span>
            <button
              onClick={() => setDraft(`Improve this selected text: "${selectedText.slice(0, 100)}"`)}
              className="text-brand-600 font-semibold hover:underline"
            >
              Ask about selection
            </button>
          </div>
        )}

        <div className="rounded-lg border border-slate-300 bg-white shadow-sm focus-within:border-brand-500 focus-within:ring-1 focus-within:ring-brand-200">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              // Enter sends; Shift+Enter starts a new line
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                sendMessage();
              }
            }}
            disabled={disabled || loading}
            placeholder={placeholder}
            rows={2}
            maxLength={4000}
            className="w-full resize-none border-0 bg-transparent px-2.5 py-1.5 text-xs text-slate-800 outline-none placeholder:text-slate-400"
          />
          <div className="flex items-center justify-between px-2 pb-1.5">
            <span className="hidden lg:inline text-xs text-slate-400">Enter to send · Shift+Enter for a new line</span>
            <div className="flex items-center gap-1">
              {recognitionRef.current && (
                <button
                  type="button"
                  onClick={toggleListening}
                  className={`p-1 rounded text-slate-500 hover:text-slate-800 transition ${
                    isListening ? 'bg-rose-100 text-rose-600 animate-pulse' : 'hover:bg-slate-100'
                  }`}
                  title={isListening ? 'Listening… click to stop' : 'Voice input'}
                >
                  {isListening ? <MicOff className="h-3 w-3" /> : <Mic className="h-3 w-3" />}
                </button>
              )}
              <button
                type="button"
                onClick={sendMessage}
                disabled={disabled || loading || !draft.trim()}
                className="inline-flex items-center gap-1 rounded bg-brand-600 px-2.5 py-1 text-xs font-semibold text-white transition hover:bg-brand-700 disabled:bg-slate-200 disabled:text-slate-400"
              >
                {loading ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default EditorChatPanel;
