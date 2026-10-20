import { User, Club, ClubMember, Person, AuditLog, ClubPermissions, TemplateDetail, GeneratedDocument, ExtractResult, Invite, Venue, NumberingSeries, Asset, RoleHeld, ClubSearchResult, JoinRequest, HomeUnderstandResponse, HomeGenerateResponse, HomeCreateResponse, HomeGeneratedDoc, ClubAnalytics, VerificationResult } from '../types';

function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
}

// The free backend host sleeps when idle and takes up to a minute to wake. While it does, the
// proxy answers 502/503/504 or the connection fails. Safe (GET) requests wait and retry, and the
// app shows a "waking up" notice instead of an error.
const WAKE_DEADLINE_MS = 90_000;
const WAKE_STATUSES = new Set([502, 503, 504]);
export const SERVER_WAKING_EVENT = 'clubdocs-server-waking';

function announceWaking(waking: boolean) {
  window.dispatchEvent(new CustomEvent(SERVER_WAKING_EVENT, { detail: { waking } }));
}

async function fetchWithWake(url: string, init: RequestInit): Promise<Response> {
  const method = (init.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD') return fetch(url, init);

  const started = Date.now();
  let attempt = 0;
  let waking = false;
  try {
    for (;;) {
      try {
        const res = await fetch(url, init);
        if (!WAKE_STATUSES.has(res.status) || Date.now() - started > WAKE_DEADLINE_MS) return res;
      } catch (err) {
        if (Date.now() - started > WAKE_DEADLINE_MS) throw err;
      }
      if (!waking) {
        waking = true;
        announceWaking(true);
      }
      attempt += 1;
      await new Promise((r) => setTimeout(r, Math.min(2000 * attempt, 8000)));
    }
  } finally {
    if (waking) announceWaking(false);
  }
}

let refreshPromise: Promise<boolean> | null = null;

async function attemptTokenRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const res = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Include CSRF token for state-changing requests
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrfToken = getCookie('csrf_token');
    if (csrfToken) {
      headers.set('X-CSRF-Token', csrfToken);
    }
  }

  let res = await fetchWithWake(`/api/v1${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  // Auto-refresh token on 401 for non-auth endpoints
  const isAuthRoute = endpoint.startsWith('/auth/');
  if (res.status === 401 && !isAuthRoute) {
    const refreshed = await attemptTokenRefresh();
    if (refreshed) {
      const retryHeaders = new Headers(options.headers || {});
      if (!retryHeaders.has('Content-Type') && !(options.body instanceof FormData)) {
        retryHeaders.set('Content-Type', 'application/json');
      }
      const csrfToken = getCookie('csrf_token');
      if (csrfToken && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
        retryHeaders.set('X-CSRF-Token', csrfToken);
      }
      res = await fetch(`/api/v1${endpoint}`, {
        ...options,
        headers: retryHeaders,
        credentials: 'include',
      });
    }
  }

  if (!res.ok) {
    let errorDetail = 'Request failed';
    let rawDetail: any = undefined;
    try {
      const data = await res.json();
      rawDetail = data?.detail;
      if (typeof data.detail === 'string') {
        errorDetail = data.detail;
      } else if (data.detail && typeof data.detail === 'object') {
        if (Array.isArray(data.detail)) {
          errorDetail = data.detail.map((err: any) => err.msg || err.message || JSON.stringify(err)).join('; ');
        } else if (data.detail.message) {
          errorDetail = data.detail.message;
        } else {
          errorDetail = JSON.stringify(data.detail);
        }
      } else if (typeof data.message === 'string') {
        errorDetail = data.message;
      } else {
        errorDetail = JSON.stringify(data);
      }
    } catch {
      errorDetail = `${res.status} ${res.statusText}`;
    }

    if (res.status === 401 && !isAuthRoute) {
      errorDetail = 'Your session has expired. Please sign in again.';
    }

    // Keep status and structured detail so callers can react (e.g. 409 unreviewed AI items).
    const error = new Error(errorDetail) as Error & { status?: number; detail?: any };
    error.status = res.status;
    error.detail = rawDetail;
    throw error;
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}

export const api = {
  auth: {
    me: () => apiFetch<User>('/auth/me'),
    updateProfile: (name: string) =>
      apiFetch<User>('/auth/me', { method: 'PATCH', body: JSON.stringify({ name }) }),
    changePassword: (newPassword: string, currentPassword?: string) =>
      apiFetch<{ user: User }>('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: currentPassword || null, new_password: newPassword }),
      }),
    signOutOthers: () => apiFetch<{ user: User }>('/auth/sign-out-others', { method: 'POST' }),
    google: async (credential: string, invite_code?: string) => {
      const res = await apiFetch<{ message: string; user: User; access_token?: string; refresh_token?: string; csrf_token?: string }>('/auth/google', {
        method: 'POST',
        body: JSON.stringify({ credential, invite_code }),
      });
      return res;
    },
    login: async (formData: URLSearchParams) => {
      const res = await apiFetch<{ message: string; user: User; access_token?: string; refresh_token?: string; csrf_token?: string }>('/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
      });
      return res;
    },
    register: async (data: { email: string; password: string; full_name: string; invite_code?: string }) => {
      const res = await apiFetch<{ message: string; user: User; access_token?: string; refresh_token?: string; csrf_token?: string }>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          email: data.email,
          password: data.password,
          full_name: data.full_name,
          name: data.full_name,
          invite_code: data.invite_code,
        }),
      });
      return res;
    },
    forgotPassword: (email: string) =>
      apiFetch<{ message: string }>('/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      }),
    resetPassword: (token: string, new_password: string) =>
      apiFetch<{ message: string }>('/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, new_password }),
      }),
    logout: async () => {
      try {
        await apiFetch<{ message: string }>('/auth/logout', {
          method: 'POST',
        });
      } finally {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('csrf_token');
        localStorage.removeItem('activeClubId');
      }
    },
  },

  invites: {
    preview: (code: string) =>
      apiFetch<{
        code: string;
        club_id: string;
        club_name: string;
        club_slug: string;
        role: string;
        expires_at?: string;
        max_uses: number;
        use_count: number;
        is_valid: boolean;
        status: string;
      }>(`/invites/${code}`),
    accept: (code: string, clubId?: string) =>
      apiFetch<{ message: string; club_id: string; role: string }>(`/invites/${code}/accept`, {
        method: 'POST',
        body: JSON.stringify(clubId ? { club_id: clubId } : {}),
      }),
  },

  clubs: {
    list: () => apiFetch<Club[]>('/clubs/'),
    search: (q: string = '') => apiFetch<ClubSearchResult[]>(`/clubs/search?q=${encodeURIComponent(q)}`),
    createClub: (data: { name: string; short_name: string; chapter_code?: string; position?: string; is_signatory?: boolean }) =>
      apiFetch<Club>('/clubs', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    joinRequest: (clubId: string | number, data: { position: string; requested_role?: 'editor' | 'viewer'; message?: string }) =>
      apiFetch<JoinRequest>(`/clubs/${clubId}/join-requests`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    updatePosition: (clubId: string | number, position: string) =>
      apiFetch<{ status: string; position: string }>(`/clubs/${clubId}/position`, {
        method: 'PUT',
        body: JSON.stringify({ position }),
      }),
    getMyJoinRequest: (clubId: string | number) =>
      apiFetch<JoinRequest | null>(`/clubs/${clubId}/join-requests/my`),
    listJoinRequests: (clubId: string | number) =>
      apiFetch<JoinRequest[]>(`/clubs/${clubId}/join-requests`),
    approveJoinRequest: (clubId: string | number, reqId: string, data: { role: string; is_signatory?: boolean; signatory_role?: string; conflict_resolution?: string }) =>
      apiFetch<void>(`/clubs/${clubId}/join-requests/${reqId}/approve`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    rejectJoinRequest: (clubId: string | number, reqId: string) =>
      apiFetch<void>(`/clubs/${clubId}/join-requests/${reqId}/reject`, {
        method: 'POST',
      }),
    cancelJoinRequest: (clubId: string | number, reqId: string) =>
      apiFetch<JoinRequest>(`/clubs/${clubId}/join-requests/${reqId}/cancel`, {
        method: 'POST',
      }),
    get: (clubId: string | number) => apiFetch<Club>(`/clubs/${clubId}`),
    update: (clubId: string | number, data: any) =>
      apiFetch<Club>(`/clubs/${clubId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    getMembers: (clubId: string | number) => apiFetch<ClubMember[]>(`/clubs/${clubId}/members`),
    addMember: (clubId: string | number, data: { user_email: string; role: string; title?: string }) =>
      apiFetch<ClubMember>(`/clubs/${clubId}/members`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    removeMember: (clubId: string | number, memberId: string | number) =>
      apiFetch<void>(`/clubs/${clubId}/members/${memberId}`, {
        method: 'DELETE',
      }),
    getPermissions: (clubId: string | number) => apiFetch<ClubPermissions>(`/clubs/${clubId}/permissions`),
    getAuditLogs: (clubId: string | number) => apiFetch<AuditLog[]>(`/clubs/${clubId}/audit-logs`),
    getPeople: (clubId: string | number) => apiFetch<Person[]>(`/clubs/${clubId}/people`),
    getPositions: (clubId: string | number) =>
      apiFetch<{ key: string; label: string; group: 'faculty' | 'student' | 'staff' | 'other'; signs: boolean; help: string }[]>(`/clubs/${clubId}/positions`),
    addPerson: (clubId: string | number, person: Partial<Person>) =>
      apiFetch<Person>(`/clubs/${clubId}/people`, {
        method: 'POST',
        body: JSON.stringify(person),
      }),
    updatePerson: (clubId: string | number, personId: string | number, data: Partial<Person>) =>
      apiFetch<Person>(`/clubs/${clubId}/people/${personId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deletePerson: (clubId: string | number, personId: string | number) =>
      apiFetch<{ message: string }>(`/clubs/${clubId}/people/${personId}`, {
        method: 'DELETE',
      }),
    assignRole: (clubId: string | number, data: { person_id: string; role_key: string; designation_label: string; academic_year: string }) =>
      apiFetch<RoleHeld>(`/clubs/${clubId}/roles`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    updateRole: (clubId: string | number, roleId: string, data: { role_key?: string; designation_label?: string; academic_year?: string }) =>
      apiFetch<RoleHeld>(`/clubs/${clubId}/roles/${roleId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deleteRole: (clubId: string | number, roleId: string) =>
      apiFetch<{ message: string }>(`/clubs/${clubId}/roles/${roleId}`, {
        method: 'DELETE',
      }),
    revealSensitive: (clubId: string | number, personId: string | number) =>
      apiFetch<{ field: string; value: string | null }>(`/clubs/${clubId}/people/${personId}/sensitive?reveal=true`),
    getInvites: (clubId: string | number) => apiFetch<Invite[]>(`/clubs/${clubId}/invites`),
    createInvite: (clubId: string | number, data: { role: string; max_uses?: number; expiry_days?: number }) =>
      apiFetch<Invite>(`/clubs/${clubId}/invites`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    revokeInvite: (clubId: string | number, inviteId: string) =>
      apiFetch<{ message: string }>(`/clubs/${clubId}/invites/${inviteId}/revoke`, {
        method: 'POST',
      }),
    getVenues: (clubId: string | number) => apiFetch<Venue[]>(`/clubs/${clubId}/venues`),
    createVenue: (clubId: string | number, data: Partial<Venue>) =>
      apiFetch<Venue>(`/clubs/${clubId}/venues`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    updateVenue: (clubId: string | number, venueId: string, data: Partial<Venue>) =>
      apiFetch<Venue>(`/clubs/${clubId}/venues/${venueId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deleteVenue: (clubId: string | number, venueId: string) =>
      apiFetch<{ message: string }>(`/clubs/${clubId}/venues/${venueId}`, {
        method: 'DELETE',
      }),
    getNumberingSeries: (clubId: string | number) => apiFetch<NumberingSeries[]>(`/clubs/${clubId}/numbering`),
    updateNumberingSeries: (clubId: string | number, seriesKey: string, data: { format?: string; academic_year?: string; description?: string }) =>
      apiFetch<NumberingSeries>(`/clubs/${clubId}/numbering/${seriesKey}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    getAssets: (clubId: string | number) => apiFetch<Asset[]>(`/clubs/${clubId}/assets`),
    setBranding: (clubId: string | number, data: { logo_asset_id?: string }) =>
      apiFetch<{ logo_asset_id: string | null }>(`/clubs/${clubId}/branding`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    uploadLogo: async (clubId: string | number, file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return apiFetch<{ asset_id: string; filename: string; url: string; letterhead_id: string }>(`/clubs/${clubId}/logo`, {
        method: 'POST',
        body: formData,
      });
    },
    setupWizard: (clubId: string | number, data: any) =>
      apiFetch<{ message: string; club: Club }>(`/clubs/${clubId}/setup-wizard`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getStorageStats: (clubId: string | number) =>
      apiFetch<{
        club_id: string;
        club_name: string;
        usage: {
          documents_bytes: number;
          documents_files: number;
          previews_bytes: number;
          previews_files: number;
          templates_bytes: number;
          templates_files: number;
          total_bytes: number;
          total_mb: number;
        };
        retention_settings: {
          keep_version_files: number;
          preview_ttl_days: number;
          batch_ttl_hours: number;
          description: string;
        };
      }>(`/clubs/${clubId}/storage-stats`),
    runStorageGc: (clubId: string | number) =>
      apiFetch<{
        message: string;
        freed_bytes: number;
        orphans_removed: number;
        expired_previews_removed: number;
        expired_batches_removed: number;
        pruned_versions_removed: number;
      }>(`/clubs/${clubId}/storage-gc`, {
        method: 'POST',
      }),
  },

  documents: {
    getTemplateSchema: (clubId: string | number, templateId: string) =>
      apiFetch<TemplateDetail>(`/clubs/${clubId}/documents/templates/${templateId}/schema`),
    extract: (clubId: string | number, text: string) =>
      apiFetch<ExtractResult>(`/clubs/${clubId}/documents/extract`, {
        method: 'POST',
        body: JSON.stringify({ text }),
      }),
    reserveNumber: (
      clubId: string | number,
      seriesKey: string,
      payload?: { template_id?: string; event_code?: string }
    ) =>
      apiFetch<{ reservation_id: string; ref_no: string; series_key: string; academic_year: string; expires_at: string }>(
        `/clubs/${clubId}/numbering/${seriesKey}/reserve`,
        {
          method: 'POST',
          body: JSON.stringify(payload || {}),
        }
      ),
    generate: (
      clubId: string | number,
      payload: {
        template_id: string;
        event_id?: string;
        title?: string;
        ref_no?: string;
        ref_no_confirmed: boolean;
        reservation_id?: string;
        event_data: Record<string, any>;
        confirmed_fields: string[];
        deferred_fields?: string[];
      }
    ) =>
      apiFetch<GeneratedDocument>(`/clubs/${clubId}/documents/generate`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    list: (
      clubId: string | number,
      params?: {
        q?: string;
        template_id?: string;
        status?: string;
        event_id?: string;
        date_from?: string;
        date_to?: string;
        sort_by?: string;
        sort_order?: string;
        page?: number;
        page_size?: number;
      }
    ) => {
      const searchParams = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== '') {
            searchParams.append(k, String(v));
          }
        });
      }
      const qs = searchParams.toString();
      return apiFetch<{
        items: Array<{
          id: string;
          club_id: string;
          template_id: string;
          template_slug: string;
          template_name: string;
          event_id?: string;
          event_title?: string;
          title: string;
          ref_no?: string;
          status: string;
          created_at: string;
          created_by?: string;
          current_version_no: number;
          page_count: number;
          docx_url: string;
          pdf_url: string;
        }>;
        total: number;
        page: number;
        page_size: number;
        total_pages: number;
      }>(`/clubs/${clubId}/documents${qs ? `?${qs}` : ''}`);
    },
    get: (clubId: string | number, docId: string) =>
      apiFetch<GeneratedDocument>(`/clubs/${clubId}/documents/${docId}`),
    revise: (clubId: string | number, docId: string, changes: Record<string, any>, note?: string) =>
      apiFetch<{ version_no: number; status: string; change_summary: string }>(`/clubs/${clubId}/documents/${docId}/revise`, {
        method: 'POST',
        body: JSON.stringify({ changes, note }),
      }),
    review: (
      clubId: string | number,
      docId: string,
      action: 'submit' | 'approve' | 'request-changes' | 'comments',
      comment?: string
    ) =>
      apiFetch<{ status?: string; verification_code?: string }>(`/clubs/${clubId}/documents/${docId}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ comment }),
      }),
    email: (clubId: string | number, docId: string, payload: { to: string[]; message?: string; attach: 'pdf' | 'docx' | 'both' }) =>
      apiFetch<{ sent_to: string[] }>(`/clubs/${clubId}/documents/${docId}/email`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    parseRows: (clubId: string | number, templateId: string, source: { file?: File; sheetUrl?: string }) => {
      const form = new FormData();
      form.append('template_id', templateId);
      if (source.file) form.append('file', source.file);
      if (source.sheetUrl) form.append('sheet_url', source.sheetUrl);
      return apiFetch<{
        headers: string[];
        rows: Record<string, string>[];
        row_count: number;
        fields: { key: string; label: string; required: boolean }[];
        mapping: Record<string, string | null>;
      }>(`/clubs/${clubId}/documents/rows/parse`, { method: 'POST', body: form });
    },
    getTemplateSamplePages: (clubId: string | number, templateId: string) =>
      apiFetch<{ name: string; description?: string; page_count: number; pages: string[] }>(
        `/clubs/${clubId}/documents/templates/${templateId}/sample-pages`
      ),
    listTemplates: (clubId: string | number) =>
      apiFetch<any[]>(`/clubs/${clubId}/documents/templates`),
    forkTemplate: (clubId: string | number, templateId: string, payload?: { name?: string }) =>
      apiFetch<any>(`/clubs/${clubId}/documents/templates/${templateId}/fork`, {
        method: 'POST',
        body: payload ? JSON.stringify(payload) : undefined,
      }),
    updateTemplate: (
      clubId: string | number,
      templateId: string,
      data: { name?: string; description?: string; category?: string; status?: string }
    ) =>
      apiFetch<any>(`/clubs/${clubId}/documents/templates/${templateId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deleteTemplate: (clubId: string | number, templateId: string) =>
      apiFetch<any>(`/clubs/${clubId}/documents/templates/${templateId}`, {
        method: 'DELETE',
      }),
    createBlankTemplate: (
      clubId: string | number,
      data: { name: string; category?: string; description?: string }
    ) =>
      apiFetch<any>(`/clubs/${clubId}/documents/templates/blank`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getTemplateDraft: (clubId: string | number, templateId: string) =>
      apiFetch<any>(`/clubs/${clubId}/documents/templates/${templateId}/draft`),
    saveTemplateDraft: (clubId: string | number, templateId: string, data: any) =>
      apiFetch<any>(`/clubs/${clubId}/documents/templates/${templateId}/draft`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    compileTemplate: (clubId: string | number, templateId: string, data: any) =>
      apiFetch<any>(`/clubs/${clubId}/documents/templates/${templateId}/compile`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    previewTemplate: (clubId: string | number, templateId: string, data: any) =>
      apiFetch<{ pages: string[]; page_count: number }>(`/clubs/${clubId}/documents/templates/${templateId}/preview`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    publishTemplate: (clubId: string | number, templateId: string) =>
      apiFetch<any>(`/clubs/${clubId}/documents/templates/${templateId}/publish`, {
        method: 'POST',
      }),
    reviewAiTemplate: (
      clubId: string | number,
      templateId: string,
      payload: { all?: boolean; field_keys?: string[]; block_indices?: number[] }
    ) =>
      apiFetch<any>(`/clubs/${clubId}/documents/templates/${templateId}/review-ai`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    aiDraftTemplate: (
      clubId: string | number,
      data: { description: string }
    ) =>
      apiFetch<{
        template: any;
        draft: any;
        logo_resolution: any;
        message: string;
      }>(`/clubs/${clubId}/documents/templates/ai-draft`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    resolveLogo: (
      clubId: string | number,
      text: string
    ) =>
      apiFetch<{
        status: 'resolved' | 'ambiguous' | 'not_found';
        asset_id?: string;
        filename?: string;
        url?: string;
        candidates?: any[];
        message?: string;
      }>(`/clubs/${clubId}/documents/assets/resolve-logo`, {
        method: 'POST',
        body: JSON.stringify({ text }),
      }),
    getWizardQuestions: (clubId: string | number, prompt: string) =>
      apiFetch<{ prompt: string; questions: Array<{ id: string; question: string; category: string; options: string[] }>; suggested_title: string }>(
        `/clubs/${clubId}/documents/templates/wizard/questions`,
        {
          method: 'POST',
          body: JSON.stringify({ prompt }),
        }
      ),
    generateFromWizard: (clubId: string | number, data: { prompt: string; answers: Record<string, string>; numbering_series?: string }) =>
      apiFetch<any>(`/clubs/${clubId}/documents/templates/wizard/generate`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    importTextTemplate: (clubId: string | number, data: { text: string; name?: string }) =>
      apiFetch<{ editor_json: any; fields: any[]; name: string }>(`/clubs/${clubId}/documents/templates/import/text`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    importDocxTemplate: async (clubId: string | number, file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return apiFetch<{ editor_json: any; fields: any[]; unsupported_elements: string[]; name: string }>(
        `/clubs/${clubId}/documents/templates/import/docx`,
        {
          method: 'POST',
          body: formData,
        }
      );
    },
    improveText: (clubId: string | number, data: { text: string; mode?: string }) =>
      apiFetch<{ original: string; improved: string; mode: string; explanation: string; diff: { before: string; after: string } }>(
        `/clubs/${clubId}/documents/improve-text`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      ),
    suggestDetails: (clubId: string | number, data: { event_type: string; existing_fields?: string[] }) =>
      apiFetch<{ suggestions: Array<{ key: string; label: string; type: string; ask: string; sample: string; required: boolean; ai_suggested: boolean }> }>(
        `/clubs/${clubId}/documents/suggest-details`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      ),
    checkTemplate: (clubId: string | number, templateId: string, data: any) =>
      apiFetch<{ score: number; total_findings: number; findings: any[] }>(
        `/clubs/${clubId}/documents/templates/${templateId}/check`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      ),
    translateTemplate: (clubId: string | number, templateId: string, data: { target_lang: string; editor_json?: any }) =>
      apiFetch<{ editor_json: any; design_settings: any; target_lang: string }>(
        `/clubs/${clubId}/documents/templates/${templateId}/translate`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      ),
  },
  events: {
    list: (clubId: string | number) =>
      apiFetch<{ items: any[]; total: number }>(`/clubs/${clubId}/events`),
    listActive: (clubId: string | number) =>
      apiFetch<any[]>(`/clubs/${clubId}/events/active`),
    get: (clubId: string | number, eventId: string) =>
      apiFetch<any>(`/clubs/${clubId}/events/${eventId}`),
    create: (clubId: string | number, payload: { title: string; event_code?: string; record?: Record<string, any> }) =>
      apiFetch<any>(`/clubs/${clubId}/events`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    update: (clubId: string | number, eventId: string, payload: { title?: string; event_code?: string; record?: Record<string, any> }, updateDocuments = false) =>
      apiFetch<any>(`/clubs/${clubId}/events/${eventId}?update_documents=${updateDocuments}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
  },
  analytics: {
    get: (clubId: string | number) => apiFetch<ClubAnalytics>(`/clubs/${clubId}/analytics`),
  },
  verify: {
    get: (code: string) => apiFetch<VerificationResult>(`/verify/${encodeURIComponent(code)}`),
    file: (code: string, file: File) => {
      const form = new FormData();
      form.append('file', file);
      return apiFetch<VerificationResult>(`/verify/${encodeURIComponent(code)}`, { method: 'POST', body: form });
    },
  },
  home: {
    create: (
      clubId: string | number,
      payload: {
        text: string;
        selected_template_id?: string | null;
      }
    ) =>
      apiFetch<HomeCreateResponse>(`/clubs/${clubId}/home/create`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    applyAll: (
      clubId: string | number,
      payload: {
        event_id: string;
        updates: Record<string, any>;
      }
    ) =>
      apiFetch<{
        event_id: string;
        updated_documents_count: number;
        documents: HomeGeneratedDoc[];
      }>(`/clubs/${clubId}/home/apply-all`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    addDocument: (
      clubId: string | number,
      payload: {
        event_id: string;
        template_id: string;
      }
    ) =>
      apiFetch<HomeGeneratedDoc>(`/clubs/${clubId}/home/add-document`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    aiInstruct: (
      clubId: string | number,
      payload: {
        instruction: string;
        current_data: Record<string, any>;
        template_slug?: string;
      }
    ) =>
      apiFetch<{
        proposed_updates: Record<string, any>;
        explanation: string;
      }>(`/clubs/${clubId}/home/ai-instruct`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),

    understand: (
      clubId: string | number,
      payload: {
        text: string;
        explicit_data?: Record<string, any>;
        selected_template_ids?: string[];
      }
    ) =>
      apiFetch<HomeUnderstandResponse>(`/clubs/${clubId}/home/understand`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    generate: (
      clubId: string | number,
      payload: {
        selected_template_ids: string[];
        event_data: Record<string, any>;
        ref_numbers_accepted: boolean;
        event_id?: string;
        event_title?: string;
        allow_blanks?: boolean;
      }
    ) =>
      apiFetch<HomeGenerateResponse>(`/clubs/${clubId}/home/generate`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
  },
};
