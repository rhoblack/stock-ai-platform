/**
 * v0.9 Phase B — thin logging utility.
 *
 * Centralises console output so:
 *  - In tests (vitest), log output can be suppressed or spied on in one place.
 *  - In production, the calls can be wired to a monitoring service without
 *    touching every call-site.
 *
 * Sensitive values must NOT be passed to any of these functions — callers are
 * responsible for scrubbing before logging.
 */

const isDev = import.meta.env.DEV

export const logger = {
  /** Log a non-fatal error with optional context. */
  error(message: string, ...args: unknown[]): void {
    if (isDev) {
      console.error(`[ERROR] ${message}`, ...args)
    }
    // Production: wire to monitoring here (e.g. sentry.captureMessage)
  },

  /** Log a warning. */
  warn(message: string, ...args: unknown[]): void {
    if (isDev) {
      console.warn(`[WARN] ${message}`, ...args)
    }
  },

  /** Log an informational message (dev only — no-op in production). */
  info(message: string, ...args: unknown[]): void {
    if (isDev) {
      console.info(`[INFO] ${message}`, ...args)
    }
  },
}
