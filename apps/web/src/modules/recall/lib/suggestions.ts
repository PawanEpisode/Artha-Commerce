/** Words and rules for AI card suggestions (R2-W5). Pure, so the sentences and the button states are tested without a screen. */
import { ApiError } from '~/lib/api'

import type { AiOverview, AiSource, Suggestion, SuggestionBatch } from './schemas'

export const SOURCE_LABEL: Record<AiSource, { title: string; help: string }> = {
  notes: { title: 'My notes and highlights', help: 'What you wrote or highlighted for this chapter.' },
  wrong_answers: { title: 'Questions I got wrong', help: 'The explanations of questions you missed in this chapter.' },
  pasted: { title: 'Text I paste', help: 'A passage you paste below. It is used once and not kept.' },
}

export const isActive = (b: Pick<SuggestionBatch, 'status'>): boolean => b.status === 'queued' || b.status === 'running'

/** How often the batch is read while the model works, in ms: quickly at first, then calmer. Null once it is finished. */
export function pollInterval(b: Pick<SuggestionBatch, 'status'> | undefined, ageMs: number): number | null {
  if (!b || !isActive(b)) return null
  return ageMs < 20_000 ? 2_000 : 4_000
}

/** What is left of today's allowance, in her words. */
export function quotaText(q: AiOverview['quota']): string {
  const batches = Math.max(q.batches_limit - q.batches_used, 0)
  const cards = Math.max(q.suggestions_limit - q.suggestions_used, 0)
  if (batches === 0) return 'You have used all of today’s requests. They come back tomorrow.'
  if (cards === 0) return 'You have used all of today’s suggestions. They come back tomorrow.'
  return `Today you can ask ${batches} more ${batches === 1 ? 'time' : 'times'} for up to ${cards} suggestions.`
}

export function canAsk(q: AiOverview['quota'], count: number): boolean {
  return q.batches_used < q.batches_limit && q.suggestions_used + count <= q.suggestions_limit
}

/** The count the stepper may reach: the batch size limit, and what is left of the day. */
export const maxCount = (o: AiOverview): number =>
  Math.max(Math.min(o.limits.max_count, o.quota.suggestions_limit - o.quota.suggestions_used), 0)

export interface RequestDraft {
  chapterId: string | null
  sources: AiSource[]
  pasted: string
  count: number
}

/** Why "Suggest cards" is not ready yet, or null when it is. */
export function requestProblem(d: RequestDraft, o: AiOverview): string | null {
  if (!d.chapterId) return 'Choose a chapter first.'
  if (d.sources.length === 0) return 'Choose where the cards should come from.'
  if (d.sources.includes('pasted') && d.sources.length === 1 && d.pasted.trim().length < o.limits.min_source_chars)
    return `Paste at least ${o.limits.min_source_chars} characters of text.`
  if (!canAsk(o.quota, d.count)) return quotaText(o.quota)
  return null
}

/** The batch line under the tray: how many came back and how many the checker threw away. */
export function batchSummary(b: SuggestionBatch): string {
  if (isActive(b)) return 'Reading your material…'
  if (b.status === 'failed' || b.status === 'cancelled') return failedText(b)
  if (b.status === 'expired') return 'These suggestions have expired.'
  const dropped =
    b.dropped > 0
      ? ` ${b.dropped} ${b.dropped === 1 ? 'draft was' : 'drafts were'} left out because ${b.dropped === 1 ? 'its' : 'their'} quote was not in your material.`
      : ''
  return `${b.produced} ${b.produced === 1 ? 'suggestion' : 'suggestions'} ready.${dropped}`
}

export function failedText(b: Pick<SuggestionBatch, 'error_code'>): string {
  switch (b.error_code) {
    case 'nothing_usable':
      return 'Nothing in your material gave a card we could back with a quote. You were not charged.'
    case 'blocked':
      return 'The AI could not work with that text. You were not charged.'
    case 'too_little':
      return 'There was not enough text. You were not charged.'
    case 'consent_withdrawn':
      return 'You withdrew your agreement, so nothing was kept.'
    case 'unavailable':
      return 'AI suggestions are not available right now. You were not charged.'
    default:
      return 'Something went wrong while making suggestions. You were not charged. Try again.'
  }
}

export const pendingDrafts = (b: SuggestionBatch): Suggestion[] => b.suggestions.filter((s) => s.status === 'draft')

export const decidedText = (s: Pick<Suggestion, 'status'>): string | null =>
  s.status === 'accepted' || s.status === 'edited_accepted'
    ? 'Added to your cards'
    : s.status === 'rejected'
      ? 'Not suggested again'
      : s.status === 'expired'
        ? 'Expired'
        : null

/** "prompt_md" becomes "Prompt", "case_name" becomes "Case name". */
export const fieldLabel = (key: string): string => {
  const words = key.replace(/_md$/, '').replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** Editable fields in a stable order: the keys the draft has, longer Markdown fields as text areas. */
export const isLongField = (key: string): boolean => key.endsWith('_md')

/** One sentence for an API failure of the suggestion screens (the server's own words when it has them). */
export function suggestionFailure(error: unknown): string {
  if (error instanceof ApiError) {
    const code = error.code
    switch (code) {
      case 'ai_unavailable':
        return 'AI suggestions are not available right now. Please try again later.'
      case 'ai_not_consented':
        return 'Agree to the AI notice first.'
      case 'consent_version_mismatch':
        return 'The notice changed. Please read it again.'
      case 'quota_exceeded':
        return 'You have used today’s allowance. It comes back tomorrow.'
      case 'source_unavailable':
        return 'One of those sources is not connected yet. Choose another.'
      case 'not_enough_material':
        return 'There is not enough text in those sources. Add notes or paste more text.'
      case 'duplicate_card':
        return 'You already have a card with this text. You can reject this one.'
      case 'suggestion_decided':
        return 'You already decided this suggestion.'
      case 'invalid_fields':
        return 'That edit breaks a card rule. Check each field is filled in and not too long.'
      case 'unknown_chapter':
        return 'That chapter is not in your syllabus.'
    }
    if (error.status === 429) return 'Too many requests. Please wait a moment and try again.'
    if (error.status === 0) return 'You seem to be offline. Try again when you are connected.'
  }
  return 'Something went wrong. Please try again.'
}
