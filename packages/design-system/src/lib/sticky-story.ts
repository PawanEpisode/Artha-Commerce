/** Map a 0–1 scene progress to a step index. `progress` outside 0–1 is clamped. */
export function stepIndexFromProgress(progress: number, count: number): number {
  if (count <= 1) return 0
  const p = Number.isFinite(progress) ? Math.min(1, Math.max(0, progress)) : 0
  return Math.min(count - 1, Math.floor(p * count))
}

/**
 * Same mapping, but stay on `previous` until progress has crossed the bucket edge by
 * `hysteresis` (as a fraction of one bucket) so adjacent steps do not flicker.
 */
export function stickyStepIndex(progress: number, count: number, previous: number, hysteresis = 0.12): number {
  const next = stepIndexFromProgress(progress, count)
  if (count <= 1 || next === previous) return next
  const bucket = 1 / count
  const edge = next > previous ? next * bucket : previous * bucket
  if (Math.abs(next - previous) === 1 && Math.abs(progress - edge) < hysteresis * bucket) {
    return Math.min(count - 1, Math.max(0, previous))
  }
  return next
}

/** Scroll offset inside a track so step `index` sits in the middle of its bucket. */
export function stickyStepScrollProgress(index: number, count: number): number {
  if (count <= 1) return 0
  const i = Math.min(count - 1, Math.max(0, index))
  return Math.min(1, (i + 0.45) / count)
}
