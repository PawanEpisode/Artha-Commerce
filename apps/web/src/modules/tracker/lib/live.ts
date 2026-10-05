const LABELS: Record<string, string> = {
  pomodoro: 'focus',
  stopwatch: 'stopwatch',
}

/**
 * Name of the other timer that should block Start, or null when nothing else is running.
 * The API sends "none" for that idle case; it is not a timer.
 */
export function otherLiveLabel(live: string | null | undefined): string | null {
  if (!live || live === 'none') return null
  return LABELS[live] ?? live
}
