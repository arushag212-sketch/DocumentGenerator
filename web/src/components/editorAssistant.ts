/** Shared editor-assistant wire types and the browser transport.
 *
 * This helper deliberately lives outside api/client.ts.  The editor assistant
 * can be embedded in other editor surfaces without expanding the global API
 * object, while still using the same cookie-authenticated `/api/v1` transport
 * conventions as the rest of the web app.
 */

export type EditorAssistantActionType =
  | 'set_document_title'
  | 'set_document_description'
  | 'add_field'
  | 'insert_block'
  | 'update_logo'
  | 'rewrite_selected_text';

export type EditorAssistantField = {
  key: string;
  label: string;
  type: string;
  required: boolean;
  importance?: 'essential' | 'optional';
  ask?: string;
  defer_ok?: boolean;
  sensitive?: boolean;
  values?: string[];
  ai_suggested?: boolean;
  [key: string]: unknown;
};

export type EditorAssistantBlock = {
  type: string;
  attrs?: Record<string, unknown>;
  content?: Array<Record<string, unknown>>;
  [key: string]: unknown;
};

export type EditorAssistantAction = {
  type: EditorAssistantActionType;
  summary: string;
  payload: {
    title?: string;
    description?: string;
    field?: EditorAssistantField;
    block?: EditorAssistantBlock;
    logo?: {
      instruction?: string;
      asset_id?: string | null;
      url?: string | null;
      requires_asset_resolution?: boolean;
      [key: string]: unknown;
    };
    instruction?: string;
    text?: string;
    original_text?: string | null;
    requires_review?: boolean;
    [key: string]: unknown;
  };
};

export type EditorAssistantDocumentContext = {
  title?: string;
  description?: string;
  fields?: Array<Record<string, unknown>>;
  blocks?: Array<Record<string, unknown>>;
};

export type EditorAssistantRequest = {
  instruction: string;
  selectedText?: string;
  documentContext?: EditorAssistantDocumentContext;
};

export type EditorAssistantResponse = {
  message: string;
  actions: EditorAssistantAction[];
  source: 'gemini' | 'local';
  fallback: boolean;
  warnings: string[];
};

export type EditorAssistantFetcher = (
  request: EditorAssistantRequest
) => Promise<EditorAssistantResponse>;

export class EditorAssistantRequestError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'EditorAssistantRequestError';
    this.status = status;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const prefix = `${name}=`;
  const cookie = document.cookie
    .split(';')
    .map(part => part.trim())
    .find(part => part.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

function toApiPayload(request: EditorAssistantRequest): Record<string, unknown> {
  return {
    instruction: request.instruction,
    selected_text: request.selectedText || undefined,
    document_context: request.documentContext || undefined,
  };
}

function endpointFor(clubId: string, templateId?: string): string {
  const encodedClub = encodeURIComponent(clubId);
  if (!templateId) return `/api/v1/clubs/${encodedClub}/editor-assistant`;
  return `/api/v1/clubs/${encodedClub}/documents/templates/${encodeURIComponent(templateId)}/assistant`;
}

/** Request structured actions from the club-scoped backend assistant. */
export async function requestEditorAssistant(
  clubId: string,
  templateId: string | undefined,
  request: EditorAssistantRequest,
  fetcher: typeof fetch = fetch
): Promise<EditorAssistantResponse> {
  const headers = new Headers({ 'Content-Type': 'application/json' });
  const csrfToken = readCookie('csrf_token');
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken);

  let response: Response;
  try {
    response = await fetcher(endpointFor(clubId, templateId), {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify(toApiPayload(request)),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unable to reach the document assistant.';
    throw new EditorAssistantRequestError(message);
  }

  let body: Partial<EditorAssistantResponse> & { detail?: unknown } = {};
  try {
    body = await response.json();
  } catch {
    // The status below still gives the panel a useful error if the server did
    // not return JSON (for example, a proxy error page).
  }

  if (!response.ok) {
    const detail = body.detail;
    const detailMessage =
      typeof detail === 'string'
        ? detail
        : detail && typeof detail === 'object' && 'message' in detail
          ? String((detail as { message?: unknown }).message)
          : `Assistant request failed (${response.status}).`;
    throw new EditorAssistantRequestError(detailMessage, response.status);
  }

  if (!body.message || !Array.isArray(body.actions)) {
    throw new EditorAssistantRequestError('The document assistant returned an incomplete response.', response.status);
  }

  return {
    message: body.message,
    actions: body.actions,
    source: body.source === 'gemini' ? 'gemini' : 'local',
    fallback: Boolean(body.fallback),
    warnings: Array.isArray(body.warnings) ? body.warnings.filter((warning): warning is string => typeof warning === 'string') : [],
  };
}

export function actionPreview(action: EditorAssistantAction): string {
  switch (action.type) {
    case 'set_document_title':
      return action.payload.title ? `Title: ${action.payload.title}` : 'Set document title';
    case 'set_document_description':
      return action.payload.description ? `Description: ${action.payload.description}` : 'Set document description';
    case 'add_field':
      return action.payload.field?.label || action.payload.field?.key || 'Add a document field';
    case 'insert_block':
      return action.payload.block?.type ? `Insert ${action.payload.block.type}` : 'Insert a document block';
    case 'update_logo':
      return action.payload.logo?.instruction || action.payload.instruction || 'Update logo or letterhead';
    case 'rewrite_selected_text':
      return action.payload.text ? `Replace with: ${action.payload.text}` : 'Rewrite selected text';
    default:
      return 'Apply suggested change';
  }
}
