import { User, Club, ClubMember, Person, AuditLog, ClubPermissions, TemplateDetail, GeneratedDocument, ExtractResult } from '../types';

function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
}

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Include CSRF token for state-changing requests
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrfToken = getCookie('csrf_token') || localStorage.getItem('csrf_token');
    if (csrfToken) {
      headers.set('X-CSRF-Token', csrfToken);
    }
  }

  const res = await fetch(`/api/v1${endpoint}`, {
    ...options,
    headers,
    credentials: 'include', // sends cookies
  });

  // If a new CSRF token is provided in response, store it
  const newCsrf = res.headers.get('X-CSRF-Token');
  if (newCsrf) {
    localStorage.setItem('csrf_token', newCsrf);
  }

  if (!res.ok) {
    let errorDetail = 'Request failed';
    try {
      const data = await res.json();
      errorDetail = data.detail || JSON.stringify(data);
    } catch {
      errorDetail = `${res.status} ${res.statusText}`;
    }
    throw new Error(errorDetail);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}

export const api = {
  auth: {
    me: () => apiFetch<User>('/auth/me'),
    login: (formData: URLSearchParams) =>
      apiFetch<{ message: string; user: User }>('/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
      }),
    register: (data: { email: string; password: string; full_name: string }) =>
      apiFetch<{ message: string; user: User }>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
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
    logout: () =>
      apiFetch<{ message: string }>('/auth/logout', {
        method: 'POST',
      }),
  },

  clubs: {
    list: () => apiFetch<Club[]>('/clubs/'),
    get: (clubId: string | number) => apiFetch<Club>(`/clubs/${clubId}`),
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
    addPerson: (clubId: string | number, person: Partial<Person>) =>
      apiFetch<Person>(`/clubs/${clubId}/people`, {
        method: 'POST',
        body: JSON.stringify(person),
      }),
    revealSensitive: (clubId: string | number, personId: string | number) =>
      apiFetch<{ field: string; value: string | null }>(`/clubs/${clubId}/people/${personId}/sensitive?reveal=true`),
    setupWizard: (clubId: string | number, data: any) =>
      apiFetch<{ message: string; club: Club }>(`/clubs/${clubId}/setup-wizard`, {
        method: 'POST',
        body: JSON.stringify(data),
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
    get: (clubId: string | number, docId: string) =>
      apiFetch<GeneratedDocument>(`/clubs/${clubId}/documents/${docId}`),
  },
  events: {
    list: (clubId: string | number) =>
      apiFetch<{ items: any[]; total: number }>(`/clubs/${clubId}/events`),
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
};
