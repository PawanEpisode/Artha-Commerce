const DAY_MS = 86_400_000

/** "2 May 2027": the Indian 12-month format used across the app. */
export const formatDate = (iso: string | null | undefined): string =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : ''

/** "4:30 pm" in the student's time zone. */
export const formatTime = (iso: string): string =>
  new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })

/** "Just now", "5 minutes ago", "Yesterday", or a date. */
export function relativeTime(iso: string, now: number = Date.now()): string {
  const diff = now - new Date(iso).getTime()
  if (diff < 60_000) return 'Just now'
  if (diff < 3_600_000) {
    const minutes = Math.floor(diff / 60_000)
    return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  }
  if (diff < DAY_MS) {
    const hours = Math.floor(diff / 3_600_000)
    return `${hours} hour${hours === 1 ? '' : 's'} ago`
  }
  if (diff < 2 * DAY_MS) return 'Yesterday'
  return formatDate(iso)
}

/** Whole days left before the trash purges a note ("In Trash until 4 Nov"), never below zero. */
export function daysLeft(purgeAfter: string | null, now: number = Date.now()): number {
  if (!purgeAfter) return 0
  return Math.max(0, Math.ceil((new Date(purgeAfter).getTime() - now) / DAY_MS))
}

export const pluralize = (n: number, word: string) => `${n.toLocaleString('en-IN')} ${word}${n === 1 ? '' : 's'}`

/** "412 MB" from bytes, at one decimal below 10. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${Math.round(kb)} KB`
  const mb = kb / 1024
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`
}
