// Hand-written API shapes for v0.2 Phase A. Replace / augment via
// `npm run openapi` (writes to src/api/types.gen.ts) starting Phase B
// once we wire screen-by-screen typed queries.

export interface HealthResponse {
  status: string
  app: string
  env: string
}
