import { useState, useRef, useEffect, useCallback } from 'react';
import { api } from '../../api/client';

export type SaveStatus = 'saved' | 'saving' | 'unsaved' | 'conflict';

interface UseEditorAutosaveOptions {
  clubId: string;
  templateId: string;
  template: any;
  editor: any;
  onSaveSuccess?: (updatedTemplate: any) => void;
  debounceMs?: number;
}

export function useEditorAutosave({
  clubId,
  templateId,
  template,
  editor,
  onSaveSuccess,
  debounceMs = 1000,
}: UseEditorAutosaveOptions) {
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('saved');
  const [isSaving, setIsSaving] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const [conflictMessage, setConflictMessage] = useState<string | null>(null);

  const timerRef = useRef<any>(null);
  const loadedVersionRef = useRef<number | null>(null);

  // Set the loaded version once per template load
  useEffect(() => {
    if (template && typeof template.version === 'number') {
      if (loadedVersionRef.current === null) {
        loadedVersionRef.current = template.version;
      }
    }
  }, [template?.version]);

  const save = useCallback(
    async (_manual = false): Promise<boolean> => {
      if (!editor || !template) return false;

      setIsSaving(true);
      setSaveStatus('saving');

      try {
        const editorJson = editor.getJSON();
        const payload: Record<string, any> = {
          name: template.name,
          category: template.category,
          description: template.description,
          fields: template.fields || [],
          editor_json: editorJson,
          letterhead_id: template.letterhead_id || null,
        };

        // If version check is enabled, pass expected_version
        if (loadedVersionRef.current !== null) {
          payload.expected_version = loadedVersionRef.current;
        }

        const updated = await api.documents.saveTemplateDraft(clubId, templateId, payload);

        // Update tracking version
        if (updated && typeof updated.version === 'number') {
          loadedVersionRef.current = updated.version;
        }

        setSaveStatus('saved');
        setConflictMessage(null);
        setLastSavedAt(new Date());

        if (onSaveSuccess) {
          onSaveSuccess(updated);
        }
        return true;
      } catch (err: any) {
        console.error('[Autosave] Failed to save draft:', err);
        if (err.status === 409 || err.message?.includes('conflict') || err.message?.includes('version')) {
          setSaveStatus('conflict');
          setConflictMessage(
            'This template was updated in another session or window. Please refresh to load the latest changes.'
          );
        } else {
          setSaveStatus('unsaved');
        }
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [clubId, templateId, template, editor, onSaveSuccess]
  );

  const markUnsaved = useCallback(() => {
    if (saveStatus !== 'conflict') {
      setSaveStatus('unsaved');
    }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      save(false);
    }, debounceMs);
  }, [save, debounceMs, saveStatus]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return {
    saveStatus,
    isSaving,
    lastSavedAt,
    conflictMessage,
    saveNow: () => save(true),
    markUnsaved,
    setSaveStatus,
    clearConflict: () => setConflictMessage(null),
  };
}
