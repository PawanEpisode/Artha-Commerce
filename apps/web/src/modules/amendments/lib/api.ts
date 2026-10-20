import { api, ApiError, publicApi } from '~/lib/api'
import { flushQueue, QueuedOffline, writeOrQueue } from '~/lib/offline-queue'

import type {
  CardFilter,
  ChapterCard,
  MyCard,
  MySummary,
  PublicCard,
  PublicDocument,
  PublicHub,
  TermArchiveRow,
} from './types'

export const newClientId = () => crypto.randomUUID()
export const AMENDMENTS_SCOPE = 'amendments'

export { QueuedOffline }

export function isFeatureDisabled(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 403) return false
  const code = (error.body as { error?: { code?: unknown } } | undefined)?.error?.code
  return code === 'feature_disabled'
}

export function errorMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (error instanceof ApiError) {
    const message = (error.body as { error?: { message?: unknown } } | undefined)?.error?.message
    if (typeof message === 'string' && message) return message
  }
  return fallback
}

// ---------------------------------------------------------------------------
// Read Endpoints
// ---------------------------------------------------------------------------

export async function fetchMySummary(): Promise<MySummary> {
  return api<MySummary>('/amendments/me/summary/')
}

export async function fetchMyCards(
  filter: CardFilter = {},
  cursor?: string | null,
  limit = 20,
): Promise<{ cards: MyCard[]; total_count: number; has_more: boolean; next_cursor: string | null }> {
  const params = new URLSearchParams()
  if (filter.applies) params.set('applies', filter.applies)
  if (filter.subject) params.set('subject', filter.subject)
  if (filter.type) params.set('type', filter.type)
  if (filter.state) params.set('state', filter.state)
  if (filter.term) params.set('term', filter.term)
  if (filter.q) params.set('q', filter.q)
  if (cursor) params.set('cursor', cursor)
  params.set('limit', String(limit))

  const qs = params.toString()
  return api(`/amendments/me/cards/${qs ? `?${qs}` : ''}`)
}

export async function fetchMyCardDetail(publicId: string): Promise<MyCard> {
  return api<MyCard>(`/amendments/me/cards/${publicId}/`)
}

export async function fetchMyArchive(): Promise<TermArchiveRow[]> {
  return api<TermArchiveRow[]>('/amendments/me/archive/')
}

export async function fetchChapterCards(chapterId: string): Promise<ChapterCard[]> {
  return api<ChapterCard[]>(`/amendments/chapters/${chapterId}/`)
}

// ---------------------------------------------------------------------------
// Mutation Endpoints (Online Direct)
// ---------------------------------------------------------------------------

export async function setCardReviewed(
  publicId: string,
  reviewed: boolean,
  clientId?: string,
): Promise<{ status: string; public_id: string; reviewed: boolean }> {
  return api(`/amendments/cards/${publicId}/reviewed/`, {
    method: 'POST',
    body: JSON.stringify({
      reviewed,
      client_id: clientId ?? newClientId(),
      client_ts: new Date().toISOString(),
    }),
  })
}

export async function setCardSaved(
  publicId: string,
  saved: boolean,
  clientId?: string,
): Promise<{ status: string; public_id: string; saved: boolean }> {
  return api(`/amendments/cards/${publicId}/saved/`, {
    method: 'POST',
    body: JSON.stringify({
      saved,
      client_id: clientId ?? newClientId(),
      client_ts: new Date().toISOString(),
    }),
  })
}

export async function bulkSetReviewed(
  publicIds: string[],
  reviewed: boolean,
  clientId?: string,
): Promise<{ updated: number; reviewed: boolean }> {
  return api('/amendments/cards/bulk-reviewed/', {
    method: 'POST',
    body: JSON.stringify({
      public_ids: publicIds,
      reviewed,
      client_id: clientId ?? newClientId(),
    }),
  })
}

export async function fileCardReport(
  publicId: string,
  kind: string,
  message: string,
): Promise<{ status: string; public_id: string; kind: string }> {
  return api(`/amendments/cards/${publicId}/report/`, {
    method: 'POST',
    body: JSON.stringify({ kind, message }),
  })
}

// ---------------------------------------------------------------------------
// Offline Queue Resilient Writers
// ---------------------------------------------------------------------------

export async function reviewCardOrQueue(publicId: string, reviewed: boolean): Promise<boolean> {
  const clientId = newClientId()
  const path = `/amendments/cards/${publicId}/reviewed/`
  const body = {
    reviewed,
    client_id: clientId,
    client_ts: new Date().toISOString(),
  }

  try {
    await writeOrQueue(
      {
        clientId,
        method: 'POST',
        path,
        body,
        label: reviewed ? 'Mark amendment reviewed' : 'Unmark amendment reviewed',
      },
      () => setCardReviewed(publicId, reviewed, clientId),
    )
    return true
  } catch (error) {
    if (error instanceof QueuedOffline) {
      return true
    }
    throw error
  }
}

export async function saveCardOrQueue(publicId: string, saved: boolean): Promise<boolean> {
  const clientId = newClientId()
  const path = `/amendments/cards/${publicId}/saved/`
  const body = {
    saved,
    client_id: clientId,
    client_ts: new Date().toISOString(),
  }

  try {
    await writeOrQueue(
      {
        clientId,
        method: 'POST',
        path,
        body,
        label: saved ? 'Bookmark amendment' : 'Remove bookmark',
      },
      () => setCardSaved(publicId, saved, clientId),
    )
    return true
  } catch (error) {
    if (error instanceof QueuedOffline) {
      return true
    }
    throw error
  }
}

export async function syncAmendmentsOfflineQueue(): Promise<void> {
  await flushQueue()
}

// ---------------------------------------------------------------------------
// Public SEO & Unauthenticated Endpoints
// ---------------------------------------------------------------------------

export async function fetchAmendmentSitemapPaths(): Promise<string[]> {
  try {
    const res = await publicApi<{ paths: Array<string | { path: string }> }>('/amendments/public/sitemap/')
    return (res?.paths ?? []).map((entry) => (typeof entry === 'string' ? entry : entry.path))
  } catch {
    return []
  }
}

export async function fetchPublicHub(): Promise<PublicHub | null> {
  return publicApi<PublicHub>('/amendments/public/hub/')
}

export async function fetchPublicDocument(slug: string): Promise<PublicDocument | null> {
  return publicApi<PublicDocument>(`/amendments/public/documents/${slug}/`)
}

export async function fetchPublicCard(publicId: string): Promise<PublicCard | null> {
  return publicApi<PublicCard>(`/amendments/public/cards/${publicId}/`)
}

export async function fetchPublicLevel(course: string, level: string): Promise<unknown> {
  return publicApi(`/amendments/public/${course}/${level}/`)
}

export async function fetchPublicTerm(course: string, level: string, term: string): Promise<unknown> {
  return publicApi(`/amendments/public/${course}/${level}/${term}/`)
}

export async function fetchPublicPaper(course: string, level: string, term: string, paper: string): Promise<unknown> {
  return publicApi(`/amendments/public/${course}/${level}/${term}/${paper}/`)
}
