const DAY_MS = 24 * 60 * 60 * 1000

/** "Last used today", "yesterday", "3 days ago", or the date for anything older than a week. */
export function formatLastSeen(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return 'Not used yet'
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return 'Not used yet'
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOf(now) - startOf(then)) / DAY_MS)
  if (days <= 0) return 'Last used today'
  if (days === 1) return 'Last used yesterday'
  if (days < 7) return `Last used ${days} days ago`
  return `Last used ${new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' }).format(then)}`
}
