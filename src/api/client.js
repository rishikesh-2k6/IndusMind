import { supabase } from '../lib/supabase';

// On Vercel the API is served from the same origin (/api/*), so an empty base
// URL (relative requests) is correct. In local dev, default to the backend on
// :8000. An explicit VITE_API_URL always wins.
export const API_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.DEV ? 'http://localhost:8000' : '');

async function authHeaders() {
  if (!supabase) return {};
  const { data } = await supabase.auth.getSession();
  const token = data?.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const headers = { ...(await authHeaders()) };
  let payload;
  if (isForm) {
    payload = body; // FormData; let the browser set the multipart boundary.
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${API_URL}${path}`, { method, headers, body: payload });

  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      message = data?.error?.message || data?.detail || message;
    } catch {
      /* response was not JSON */
    }
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  me: () => request('/api/v1/auth/me'),

  // Documents (admin)
  listDocuments: () => request('/api/v1/documents'),
  uploadDocument: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return request('/api/v1/documents/upload', { method: 'POST', body: fd, isForm: true });
  },
  documentStatus: (id) => request(`/api/v1/documents/${id}/status`),
  deleteDocument: (id) => request(`/api/v1/documents/${id}`, { method: 'DELETE' }),

  // Copilot (user)
  library: () => request('/api/v1/library'),
  query: (question, sessionId) =>
    request('/api/v1/query', {
      method: 'POST',
      body: { question, session_id: sessionId ?? null },
    }),
  summarize: (documentIds, focus) =>
    request('/api/v1/summarize', {
      method: 'POST',
      body: { document_ids: documentIds, focus: focus ?? null },
    }),
};
