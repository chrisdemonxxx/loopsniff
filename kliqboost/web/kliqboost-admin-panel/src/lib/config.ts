/**
 * Single source of truth for environment-derived runtime config.
 * Both `lib/auth.ts` and `lib/api.ts` MUST import from here.
 */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "https://api.kliqboost.online"

export const ADMIN_ROLES = ["super_admin", "admin", "staff", "support"] as const
export type AdminRole = (typeof ADMIN_ROLES)[number]

export function isAdminRole(role: string | undefined): role is AdminRole {
  return ADMIN_ROLES.includes(role as AdminRole)
}

/**
 * Returns true if the currently configured API base looks like an ngrok tunnel.
 * Used by apiFetch/auth to inject the ngrok-skip-browser-warning header without
 * spraying it on every staging/preview environment.
 */
export const USE_NGROK_HEADER =
  /ngrok|ngrok-free\.app/i.test(API_URL) ||
  process.env.NEXT_PUBLIC_USE_NGROK === "1"

/** Configurable login path, honors the obfuscation prefix when set. */
export const ADMIN_PATH_PREFIX = process.env.ADMIN_REQUIRED_PATH_PREFIX || ""
export const LOGIN_PATH = `${ADMIN_PATH_PREFIX}/login`
export const DASHBOARD_PATH = `${ADMIN_PATH_PREFIX}/dashboard`
