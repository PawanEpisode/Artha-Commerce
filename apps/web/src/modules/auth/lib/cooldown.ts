/** Resend buttons wait this long (Supabase allows one email per 60 s per address by default: `max_frequency` in supabase/config.toml). */
export const RESEND_COOLDOWN_SECONDS = 60

/** Whole seconds left until `until` (epoch ms). Computed from timestamps, so a throttled background tab stays correct. */
export function secondsRemaining(until: number, now: number): number {
  return Math.max(0, Math.ceil((until - now) / 1000))
}
