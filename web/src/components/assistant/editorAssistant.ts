/** Shared editor-assistant wire types and the browser transport.
 *
 * This helper deliberately lives outside api/client.ts. The editor assistant
 * can be embedded in other editor surfaces without expanding the global API
 * object, while still using the same cookie-authenticated `/api/v1` transport
 * conventions as the rest of the web app.
 */

export type EditorAssistantActionType =
  | 'set_title'
  | 'set_document_title'
  | 'set_description'
  | 'set_document_description'
  | 'insert_block'
  | 'update_block'
  | 'delete_block'
  | 'move_block'
  | 'duplicate_block'
  | 'set_text_style'
  | 'set_block_style'
  | 'set_theme'
  | 'set_page'
  | 'add_field'
  | 'rename_field'
  | 'set_field_property'
  | 'insert_chip'
  | 'insert_clause'
  | 'set_letterhead'
  | 'update_logo'
  | 'rewrite_text'
  | 'rewrite_selected_text'
  | 'translate_text'
  | 'proofread_text'
  | 'add_table_column'
  | 'add_table_row'
  | 'set_table_total'
  | 'ask_clarifying_question';

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
    old_key?: string;
    new_key?: string;
    new_label?: string;
    property?: string;
    value?: unknown;
    field_key?: string;
    clause_name?: string;
    block?: EditorAssistantBlock;
    block_id?: string;
    target_block_id?: string;
    position?: string;
    color?: string;
    highlight?: string;
    font?: string;
    size?: string;
    alignment?: string;
    bold?: boolean;
    italic?: boolean;
    underline?: boolean;
    line_height?: string;
    background?: string;
    border?: string;
    padding?: string;
    shading?: string;
    theme?: string;
    orientation?: string;
    margins?: string;
    watermark?: string;
    logo?: {
      instruction?: string;
      asset_id?: string | null;
      url?: string | null;
      align?: string;
      requires_asset_resolution?: boolean;
      [key: string]: unknown;
    };
    instruction?: string;
    asset_id?: string | null;
    align?: string;
    text?: string;
    original_text?: string | null;
    language?: string;
    corrections?: string[];
    requires_review?: boolean;
    column_name?: string;
    values?: unknown[];
    enabled?: boolean;
    total_label?: string;
    total_var?: string;
    question?: string;
    options?: string[];
    [key: string]: unknown;
  };
};

export type EditorAssistantDocumentContext = {
  title?: string;
  description?: string;
  fields?: Array<Record<string, unknown>>;
  blocks?: Array<Record<string, unknown>>;
  theme?: string;
  selected_block_id?: string;
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
    // If not JSON, status error handles it below
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
    case 'set_title':
    case 'set_document_title':
      return action.payload.title ? `Title: ${action.payload.title}` : 'Set document title';
    case 'set_description':
    case 'set_document_description':
      return action.payload.description ? `Description: ${action.payload.description}` : 'Set document description';
    case 'add_field':
      return action.payload.field?.label || action.payload.field?.key || 'Add a document field';
    case 'rename_field':
      return `Rename field: ${action.payload.old_key} -> ${action.payload.new_key}`;
    case 'set_field_property':
      return `Field property: ${action.payload.key}.${action.payload.property} = ${String(action.payload.value)}`;
    case 'insert_block':
      return action.payload.block?.type ? `Insert ${action.payload.block.type}` : 'Insert a document block';
    case 'update_block':
      return `Update block ${action.payload.block_id || ''}`;
    case 'delete_block':
      return `Delete block ${action.payload.block_id || ''}`;
    case 'move_block':
      return `Move block ${action.payload.block_id || ''} ${action.payload.position || 'before'} ${action.payload.target_block_id || ''}`;
    case 'duplicate_block':
      return `Duplicate block ${action.payload.block_id || ''}`;
    case 'set_text_style':
      return `Text style: ${[action.payload.color, action.payload.alignment, action.payload.font, action.payload.size].filter(Boolean).join(', ') || 'Custom'}`;
    case 'set_block_style':
      return `Block style: ${[action.payload.background, action.payload.border].filter(Boolean).join(', ') || 'Custom'}`;
    case 'set_theme':
      return `Theme: ${action.payload.theme?.replace(/_/g, ' ') || 'Official Navy'}`;
    case 'set_page':
      return `Page: ${[action.payload.orientation, action.payload.margins, action.payload.watermark].filter(Boolean).join(', ') || 'Custom'}`;
    case 'insert_chip':
      return `Field Chip: {{ ${action.payload.field_key || ''} }}`;
    case 'insert_clause':
      return `Clause: ${action.payload.clause_name || 'Standard Clause'}`;
    case 'set_letterhead':
    case 'update_logo':
      return action.payload.instruction || action.payload.logo?.instruction || 'Update letterhead';
    case 'rewrite_text':
    case 'rewrite_selected_text':
      return action.payload.text ? `Replace with: ${action.payload.text.slice(0, 120)}` : 'Rewrite text';
    case 'translate_text':
      return action.payload.text ? `(${action.payload.language || 'Hindi'}): ${action.payload.text.slice(0, 120)}` : 'Translate text';
    case 'proofread_text':
      return action.payload.text ? `Proofread: ${action.payload.text.slice(0, 120)}` : 'Proofread text';
    case 'add_table_column':
      return `Add Column: ${action.payload.column_name || 'New Column'}`;
    case 'add_table_row':
      return `Add Row (${action.payload.values?.length || 0} cells)`;
    case 'set_table_total':
      return `Table Total: ${action.payload.total_label || 'Total'} (${action.payload.total_var || 'total_amount'})`;
    case 'ask_clarifying_question':
      return action.payload.question || 'Clarifying question';
    default:
      return 'Apply suggested change';
  }
}
