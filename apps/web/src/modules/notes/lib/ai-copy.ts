import type { AiFailure } from './ai-errors'
import type { SummaryErrorCode, SummaryJob, SummarySource } from './ai-types'
import { pluralize } from './format'
import { formatEstimate, resetDateText } from './ocr-copy'
import type { Usage } from './types'

/** The words of the AI exam summary, in one place so the screens and tests agree. */
export const AI_LABEL = 'AI draft, check against the material'

export interface SummaryAllowance {
  used: number
  limit: number
  left: number
  resetsOn?: string
}

export function summaryAllowance(
  usage: Pick<Usage, 'limits' | 'used' | 'resets_on'> | undefined,
): SummaryAllowance | null {
  if (!usage) return null
  const limit = usage.limits.ai_summaries_per_month ?? 0
  const used = usage.used.ai_summaries ?? 0
  return { used, limit, left: Math.max(0, limit - used), resetsOn: usage.resets_on }
}

export function allowanceText(allowance: SummaryAllowance | null): string {
  if (!allowance) return ''
  if (allowance.limit <= 0) return 'Exam summaries are not part of your plan yet.'
  if (allowance.left <= 0) {
    const reset = resetDateText(allowance.resetsOn)
    return `You have used all ${allowance.limit} summaries this month.${reset ? ` They reset on ${reset}.` : ''}`
  }
  return `Uses 1 of your ${allowance.left} remaining summaries this month.`
}

export function progressText(job: Pick<SummaryJob, 'status' | 'estimate_seconds' | 'item_count'>): string {
  const what = `Reading ${pluralize(job.item_count, 'note and highlight')}`
  if (job.status === 'queued')
    return `${what} is waiting its turn. You can leave this page: we will have it ready here.`
  const estimate = job.estimate_seconds > 0 ? ` ${formatEstimate(job.estimate_seconds)}.` : ''
  return `Writing your summary.${estimate} You can leave this page: it will be ready here.`
}

export const failureText = (code: SummaryErrorCode | null): string => {
  switch (code) {
    case 'blocked':
      return 'The AI could not work with this text, so no summary was made. Nothing was used from your allowance.'
    case 'too_little':
      return 'There was not enough usable material to summarise. Nothing was used from your allowance.'
    case 'consent_withdrawn':
      return 'You withdrew your consent, so this request was stopped and nothing was kept.'
    case 'unavailable':
      return 'AI help was switched off before this ran. Nothing was used from your allowance.'
    default:
      return 'The summary could not be written. Nothing was used from your allowance. Please try again later.'
  }
}

export function notEnoughText(details: { items: number; min_items: number; min_chars: number }): string {
  return `Add a little more first: a summary needs at least ${details.min_items} notes or highlights with about ${details.min_chars} characters in all. This chapter has ${pluralize(details.items, 'note or highlight')} so far.`
}

/** A refusal of `POST ai/summary/` in plain words (the consent case is handled by showing the consent sheet). */
export function startFailureText(failure: AiFailure): string {
  switch (failure.reason) {
    case 'unavailable':
    case 'feature_off':
      return 'AI help is not available yet.'
    case 'budget':
      return 'AI help is busy for today. Please try again tomorrow. Nothing was used from your allowance.'
    case 'not_enough':
      return notEnoughText(failure.details)
    case 'quota': {
      const reset = resetDateText(failure.resetsOn)
      if (failure.kind === 'ai_ocr_pages') {
        return failure.limit <= 0
          ? 'Reading pages with AI is part of the paid plans.'
          : `You have used all ${failure.limit} AI pages this month.${reset ? ` They reset on ${reset}.` : ''}`
      }
      return `You have used all ${failure.limit} summaries this month.${reset ? ` They reset on ${reset}.` : ''}`
    }
    case 'invalid_pages':
      return 'That page cannot be read. Please choose a page of this file.'
    case 'nothing_to_do':
      return 'This page already has text that AI cannot improve.'
    case 'not_openable':
      return 'This file cannot be read with AI (it is locked or does not allow copying).'
    case 'not_ready':
      return 'This file is not ready yet. Please try again in a moment.'
    default:
      return 'We could not start the summary. Please try again.'
  }
}

/** Drops the trailing "## Sources" list the API puts in the body: the screen shows the same list with links. */
export function withoutSourcesSection(markdown: string): string {
  const at = markdown.lastIndexOf('\n## Sources')
  return at === -1 ? markdown : markdown.slice(0, at).trimEnd() + '\n'
}

export function sourceLabel(source: SummarySource): string {
  return source.kind === 'note' ? source.label : source.label
}

export const dropNote = (dropped: number) =>
  dropped > 0
    ? `${pluralize(dropped, 'point')} the AI could not tie to your material ${dropped === 1 ? 'was' : 'were'} left out.`
    : ''

/** Below this score Tesseract's page is "low": the offer to improve it shows (PRD FR-F03-52 names 52 as an example). */
export const LOW_CONFIDENCE = 60

export interface PageQuality {
  tone: 'low' | 'ok' | 'ai' | 'none'
  text: string
}

/** The quality indicator of one page in plain words, from where its text came from and how sure the reading was. */
export function pageQuality(source: 'native' | 'ocr' | 'ai' | undefined, conf: number | null | undefined): PageQuality {
  if (source === 'ai') return { tone: 'ai', text: 'Read by AI. Check it against the page.' }
  if (source === 'ocr') {
    return conf !== null && conf !== undefined && conf < LOW_CONFIDENCE
      ? { tone: 'low', text: `This page was read with low confidence (${conf}%).` }
      : { tone: 'ok', text: conf === null || conf === undefined ? 'Read by OCR.' : `Read by OCR (${conf}%).` }
  }
  return { tone: 'none', text: '' }
}

/** True when "Improve this page" is worth offering: a page with no usable text, or one OCR read with low confidence. */
export const canImprove = (source: 'native' | 'ocr' | 'ai' | undefined, conf: number | null | undefined): boolean =>
  source === 'ocr' && (conf === null || conf === undefined || conf < LOW_CONFIDENCE)

export function aiPagesAllowance(usage: Pick<Usage, 'limits' | 'used' | 'resets_on'> | undefined) {
  if (!usage) return null
  const limit = usage.limits.ai_ocr_pages_per_month ?? 0
  const used = usage.used.ai_ocr_pages ?? 0
  return { limit, used, left: Math.max(0, limit - used), resetsOn: usage.resets_on }
}

export function aiPagesText(allowance: ReturnType<typeof aiPagesAllowance>): string {
  if (!allowance) return ''
  if (allowance.limit <= 0) return 'Reading pages with AI is part of the paid plans.'
  if (allowance.left <= 0) return `You have used all ${allowance.limit} AI pages this month.`
  return `Uses 1 of your ${allowance.left} remaining AI pages this month.`
}

export const pageReadFailureText = (code: string | undefined): string =>
  code === 'illegible' || code === 'too_little'
    ? 'AI could not read this page well enough to keep it. Nothing was used from your allowance.'
    : 'AI could not read this page. Nothing was used from your allowance.'
