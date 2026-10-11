/**
 * What the browser sends to Sentry about the recall screens and API calls (F-15). Card text, search text and card or deck ids
 * can be personal notes or study habits, so a recall URL loses its query string and its ids, a recall event loses its request
 * body, and while a recall screen is open console and typing breadcrumbs (which can quote what the student typed) are dropped.
 */
import type { Breadcrumb, Event } from '@sentry/react'

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi
const RECALL_URL = /\/recall(\/|\?|#|$)/
const URL_KEYS = ['url', 'to', 'from'] as const

export const isRecallUrl = (value: unknown): value is string => typeof value === 'string' && RECALL_URL.test(value)

/** The URL without query, fragment and ids: `/api/v1/recall/cards/{id}/`. */
export const maskUrl = (url: string): string => url.split(/[?#]/)[0].replace(UUID, '{id}')

const onRecallPage = (): boolean => typeof window !== 'undefined' && isRecallUrl(window.location.pathname)

export function scrubBreadcrumb(breadcrumb: Breadcrumb, recallOpen: boolean = onRecallPage()): Breadcrumb | null {
  const category = breadcrumb.category ?? ''
  if (recallOpen && (category === 'console' || category.startsWith('ui.input'))) return null
  const data: Record<string, unknown> | undefined = breadcrumb.data
  if (data) {
    for (const key of URL_KEYS) {
      if (isRecallUrl(data[key])) data[key] = maskUrl(data[key])
    }
  }
  return breadcrumb
}

export function scrubEvent<T extends Event>(event: T): T {
  const request = event.request
  const recall = isRecallUrl(request?.url) || isRecallUrl(event.transaction)
  if (request && recall) {
    delete request.data
    delete request.query_string
    delete request.cookies
    if (request.url) request.url = maskUrl(request.url)
  }
  if (recall && typeof event.transaction === 'string') event.transaction = event.transaction.replace(UUID, '{id}')
  if (event.breadcrumbs) {
    event.breadcrumbs = event.breadcrumbs.flatMap((crumb) => {
      const kept = scrubBreadcrumb(crumb, recall)
      return kept ? [kept] : []
    })
  }
  return event
}
