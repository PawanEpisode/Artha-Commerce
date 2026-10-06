import type { OnboardingState } from '~/modules/personalization'

const key = (userId: string) => `setup-cards-dismissed:${userId}`

/** Steps the student skipped and can still do. Mandatory steps never appear (the gate handles them). */
export function skippedSteps(state: Pick<OnboardingState, 'steps'>, dismissed: readonly string[]): string[] {
  return state.steps
    .filter((s) => s.state === 'skipped' && s.available && !s.mandatory && !dismissed.includes(s.key))
    .map((s) => s.key)
}

export function readDismissed(userId: string): string[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(key(userId)) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === 'string') : []
  } catch {
    return []
  }
}

/** Hiding a card is a per-device preference; the step itself stays skipped and reachable from onboarding. */
export function dismiss(userId: string, step: string): string[] {
  const next = [...new Set([...readDismissed(userId), step])]
  try {
    localStorage.setItem(key(userId), JSON.stringify(next))
  } catch {
    // Storage blocked: the card comes back next visit. Harmless.
  }
  return next
}

const CARD_COPY: Record<string, { title: string; description: string }> = {
  avatar: { title: 'Add a photo', description: 'Choose an avatar or upload a photo for your account.' },
  catchup: { title: 'Mark chapters you finished', description: 'Quick catch-up brings your progress up to date now.' },
}

/** Card wording per step; an unknown step falls back to the step's own title so a new step still shows up. */
export function setupCardFor(key: string, fallbackTitle: string) {
  return CARD_COPY[key] ?? { title: fallbackTitle, description: 'Takes about a minute.' }
}
