/**
 * The last visited page (PRD 5.6): when it is reported, how it is kept on this device, and which copy wins at the
 * next sign-in. Pure helpers plus the one transport function; the hook in `hooks/useLastVisitReporter.ts` wires them
 * to the page lifecycle.
 */
import { env } from '~/lib/env'

import { cleanVisit, type Visit } from './restorable'

/** The same page reported again inside this window is skipped (mirrors the server rule). */
export const REPORT_WINDOW_MS = 60_000

export interface StoredVisit extends Visit {
  /** ISO time the student left the page. */
  at: string
}

const storageKey = (userId: string) => `last-visit:${userId}`

/** Synchronous copy on this device: it survives a failed network write and a closing tab. Keyed by user id. */
export function saveLocalVisit(userId: string, visit: Visit, now: Date = new Date()): void {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify({ ...visit, at: now.toISOString() }))
  } catch {
    // Storage blocked or full: the server copy still works.
  }
}

/** Re-validated on the way out: a tampered or outdated value is ignored, never trusted. */
export function readLocalVisit(userId: string): StoredVisit | null {
  try {
    const raw = JSON.parse(localStorage.getItem(storageKey(userId)) ?? 'null') as Partial<StoredVisit> | null
    if (!raw || typeof raw.path !== 'string' || typeof raw.at !== 'string' || Number.isNaN(Date.parse(raw.at))) {
      return null
    }
    const clean = cleanVisit(raw.path, typeof raw.search === 'string' ? raw.search : '')
    return clean ? { ...clean, at: raw.at } : null
  } catch {
    return null
  }
}

export function clearLocalVisit(userId: string): void {
  try {
    localStorage.removeItem(storageKey(userId))
  } catch {
    // Nothing to clear.
  }
}

/** Server value wins unless the copy on this device is newer (a write the server never received). */
export function newestVisit(
  server: { path: string; search: string; at: string | null } | null,
  local: StoredVisit | null,
): { path: string; search: string; at: string | null } | null {
  if (!local) return server
  if (!server?.at) return local
  return Date.parse(local.at) > Date.parse(server.at) ? local : server
}

export interface ReportMemory {
  href: string
  at: number
}

/** False for the same page again within the window (a tab flipping between hidden and visible). */
export function shouldReport(memory: ReportMemory | null, visit: Visit, now: number): boolean {
  const href = `${visit.path}?${visit.search}`
  return !(memory && memory.href === href && now - memory.at < REPORT_WINDOW_MS)
}

/**
 * Sends the visit while the page is going away. `sendBeacon` survives unload and sends no preflight: the body is
 * `text/plain` JSON and carries the token because a beacon cannot set headers. If the browser refuses the beacon
 * (queue full, unsupported), a `keepalive` fetch with the normal header does the same job.
 */
export function sendVisit(token: string, visit: Visit): void {
  const url = `${env.VITE_API_URL}/api/v1/me/last-visit/`
  const body = { path: visit.path, search: visit.search }
  try {
    if (
      typeof navigator.sendBeacon === 'function' &&
      navigator.sendBeacon(url, JSON.stringify({ ...body, t: token }))
    ) {
      return
    }
  } catch {
    // Fall through to fetch.
  }
  void fetch(url, {
    method: 'POST',
    keepalive: true,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  }).catch(() => undefined) // best effort: the local copy is already saved
}
