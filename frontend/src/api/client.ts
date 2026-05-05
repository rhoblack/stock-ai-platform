// Minimal fetch wrapper. Vite dev proxy maps /api and /health to the
// FastAPI backend (v0.1-backend-final). VITE_API_BASE_URL overrides the
// origin only for non-proxied environments (production / staging).

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

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

interface ApiFetchInit extends Omit<RequestInit, 'body'> {
  // GET-only client for v0.2 Phase A; the v0.1 backend exposes 13
  // read-only routes. Keep `body` off the public surface so callers
  // cannot accidentally introduce a POST without an explicit override.
  searchParams?: Record<string, string | number | boolean | undefined | null>
}

export async function apiFetch<T>(path: string, init: ApiFetchInit = {}): Promise<T> {
  const { searchParams, headers, ...rest } = init
  const url = buildUrl(path, searchParams)

  const res = await fetch(url, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      ...(headers ?? {}),
    },
    ...rest,
  })

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
