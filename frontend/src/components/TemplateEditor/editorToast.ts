export type ToastTone = 'success' | 'error' | 'info';

export function showEditorToast(text: string, tone: ToastTone = 'info') {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('clubdocs-toast', { detail: { text, tone } }));
  }
}
