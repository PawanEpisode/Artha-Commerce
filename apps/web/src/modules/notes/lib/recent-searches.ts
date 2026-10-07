/** Recent searches stay on this device (PRD 7.3: "kept on device only"). They are never sent anywhere. */

const KEY = 'artha:notes:recent-searches'
export const MAX_RECENT = 8

/** Newest first, no duplicates (ignoring case), capped. An empty query is not remembered. */
export function addRecent(list: readonly string[], query: string): string[] {
  const q = query.trim()
  if (!q) return [...list]
  return [q, ...list.filter((item) => item.toLowerCase() !== q.toLowerCase())].slice(0, MAX_RECENT)
}

export function loadRecent(): string[] {
  try {
    const raw = window.localStorage.getItem(KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string').slice(0, MAX_RECENT) : []
  } catch {
    return []
  }
}

export function saveRecent(list: readonly string[]): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX_RECENT)))
  } catch {
    // Storage can be blocked or full; recent searches are a convenience only.
  }
}

export function clearRecent(): void {
  try {
    window.localStorage.removeItem(KEY)
  } catch {
    // Nothing to clear.
  }
}
