// v0.10 Phase D — Provider Health API client.
//
// Endpoint:
//   GET /api/health/providers — read-only ProviderHealthMonitor snapshot
//   merged with operator opt-in flags.
//
// Policy:
//   - read-only; no PATCH / PUT / DELETE for provider toggling
//   - secret discipline mirrored from the backend: response never carries
//     api_key / token / URL query secret -- no extra masking needed here.

import { apiFetch } from './client'
import type { ProviderHealthResponse } from './types'

export function getProviderHealth(): Promise<ProviderHealthResponse> {
  return apiFetch<ProviderHealthResponse>('/api/health/providers')
}
