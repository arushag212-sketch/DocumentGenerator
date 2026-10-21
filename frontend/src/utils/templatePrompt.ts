// Remembers the sentence an AI template was drafted from, so "Create document" can
// prefill it. Per-browser convenience only; storage may be unavailable.
const key = (templateId: string) => `clubdocs:templatePrompt:${templateId}`;

export function rememberTemplatePrompt(templateId: string, prompt: string) {
  try {
    localStorage.setItem(key(templateId), prompt);
  } catch {
    /* storage disabled */
  }
}

export function recallTemplatePrompt(templateId: string): string | null {
  try {
    return localStorage.getItem(key(templateId));
  } catch {
    return null;
  }
}

export function documentNewUrl(templateId: string): string {
  const prompt = recallTemplatePrompt(templateId);
  const params = new URLSearchParams({ template: templateId });
  if (prompt) params.set('prompt', prompt);
  return `/documents/new?${params.toString()}`;
}
