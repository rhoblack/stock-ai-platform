// Minimal fetch wrapper. Vite dev proxy maps /api and /health to the
// FastAPI backend (v0.1-backend-final). VITE_API_BASE_URL overrides the
// origin only for non-proxied environments (production / staging).
//
// v0.8 Phase D: added auth token helpers, apiPost, apiDelete.
// The Bearer token (if present) is attached to every outgoing request.

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

// ---------------------------------------------------------------------------
// Auth token helpers (localStorage)
// ---------------------------------------------------------------------------

const _TOKEN_KEY = '_sai_tok'

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(_TOKEN_KEY)
  } catch {
    return null
  }
}

export function setAuthToken(token: string): void {
  try {
    localStorage.setItem(_TOKEN_KEY, token)
  } catch {
    // ignore write errors (private browsing, quota exceeded)
  }
}

export function removeAuthToken(): void {
  try {
    localStorage.removeItem(_TOKEN_KEY)
  } catch {
    // ignore
  }
}

function buildAuthHeaders(): Record<string, string> {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// ---------------------------------------------------------------------------
// Shared response parsing
// ---------------------------------------------------------------------------

async function parseResponse<T>(res: Response): Promise<T> {
  const contentType = res.headers.get('content-type') ?? ''
  let parsedBody: unknown
  if (contentType.includes('application/json')) {
    try {
      parsedBody = await res.json()
    } catch {
      parsedBody = undefined
    }
  } else {
    try {
      parsedBody = await res.text()
    } catch {
      parsedBody = undefined
    }
  }

  if (!res.ok) {
    const detail =
      parsedBody !== null &&
      typeof parsedBody === 'object' &&
      'detail' in (parsedBody as Record<string, unknown>) &&
      typeof (parsedBody as { detail?: unknown }).detail === 'string'
        ? (parsedBody as { detail: string }).detail
        : `HTTP ${res.status} ${res.statusText}`
    throw new ApiError(res.status, detail, parsedBody)
  }

  return parsedBody as T
}

// ---------------------------------------------------------------------------
// GET client
// ---------------------------------------------------------------------------

interface ApiFetchInit extends Omit<RequestInit, 'body'> {
  searchParams?: Record<string, string | number | boolean | undefined | null>
}

export async function apiFetch<T>(path: string, init: ApiFetchInit = {}): Promise<T> {
  const { searchParams, headers, ...rest } = init
  const url = buildUrl(path, searchParams)

  const res = await fetch(url, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      ...buildAuthHeaders(),
      ...(headers ?? {}),
    },
    ...rest,
  })

  return parseResponse<T>(res)
}

// ---------------------------------------------------------------------------
// POST client (v0.8 Phase D)
// ---------------------------------------------------------------------------

export async function apiPost<T, B = unknown>(path: string, body: B): Promise<T> {
  const url = buildUrl(path)
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(body),
  })
  return parseResponse<T>(res)
}

// ---------------------------------------------------------------------------
// PUT client (v0.9 Phase D)
// ---------------------------------------------------------------------------

export async function apiPut<T, B = unknown>(path: string, body: B): Promise<T> {
  const url = buildUrl(path)
  const res = await fetch(url, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(body),
  })
  return parseResponse<T>(res)
}

// ---------------------------------------------------------------------------
// PATCH client (v0.9 Phase D)
// ---------------------------------------------------------------------------

export async function apiPatch<T, B = unknown>(path: string, body: B): Promise<T> {
  const url = buildUrl(path)
  const res = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(body),
  })
  return parseResponse<T>(res)
}

// ---------------------------------------------------------------------------
// DELETE client (v0.8 Phase D)
// ---------------------------------------------------------------------------

export async function apiDelete<T>(path: string): Promise<T> {
  const url = buildUrl(path)
  const res = await fetch(url, {
    method: 'DELETE',
    headers: {
      Accept: 'application/json',
      ...buildAuthHeaders(),
    },
  })
  return parseResponse<T>(res)
}

// ---------------------------------------------------------------------------
// URL builder
// ---------------------------------------------------------------------------

function buildUrl(
  path: string,
  searchParams?: Record<string, string | number | boolean | undefined | null>,
): string {
  const base = `${API_BASE}${path}`
  if (!searchParams) return base
  const usp = new URLSearchParams()
  for (const [key, value] of Object.entries(searchParams)) {
    if (value === undefined || value === null) continue
    usp.set(key, String(value))
  }
  const qs = usp.toString()
  return qs ? `${base}?${qs}` : base
}
