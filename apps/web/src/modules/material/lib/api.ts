import { api } from '~/lib/api'

import type {
  ChapterItemsResponse,
  ChapterSummary,
  CompareResult,
  EditionDetail,
  MaterialItem,
  MaterialReportPayload,
  ProgressState,
  Provider,
  UserEditionSelection,
  UserProviderFollow,
  Work,
} from './types'

export async function fetchWorks(params?: {
  course?: string
  level?: string
  subject?: string
  provider?: string
  q?: string
}): Promise<Work[]> {
  const q = new URLSearchParams()
  if (params?.course) q.set('course', params.course)
  if (params?.level) q.set('level', params.level)
  if (params?.subject) q.set('subject', params.subject)
  if (params?.provider) q.set('provider', params.provider)
  if (params?.q) q.set('q', params.q)

  const qs = q.toString()
  const res = await api<Work[] | { works: Work[] }>(`/material/works/${qs ? `?${qs}` : ''}`)
  if (Array.isArray(res)) return res
  return res?.works ?? []
}

export async function fetchWork(workKey: string): Promise<Work & { editions: EditionDetail[] }> {
  return api<Work & { editions: EditionDetail[] }>(`/material/works/${workKey}/`)
}

export async function fetchChapterItems(workKey: string, chapterKey: string): Promise<ChapterItemsResponse> {
  return api<ChapterItemsResponse>(`/material/works/${workKey}/chapters/${chapterKey}/items/`)
}

export async function fetchChapterSummary(chapterId: string): Promise<ChapterSummary> {
  return api<ChapterSummary>(`/material/chapters/${chapterId}/summary/`)
}

export async function fetchItemDetail(itemId: string): Promise<MaterialItem> {
  return api<MaterialItem>(`/material/items/${itemId}/`)
}

export async function updateItemProgress(
  itemId: string,
  payload: {
    state: ProgressState
    note?: string
    client_ts?: string
  },
): Promise<{ status: string; progress: ProgressState; note?: string }> {
  return api<{ status: string; progress: ProgressState; note?: string }>(`/material/progress/${itemId}/`, {
    method: 'POST',
    body: JSON.stringify({
      state: payload.state,
      note: payload.note,
      client_ts: payload.client_ts || new Date().toISOString(),
    }),
  })
}

export async function batchUpdateProgress(
  items: Array<{ item_id: string; state: ProgressState; client_ts?: string }>,
): Promise<{ updated: number }> {
  return api<{ updated: number }>(`/material/progress/batch/`, {
    method: 'POST',
    body: JSON.stringify({ items }),
  })
}

export async function compareEditions(
  workKey: string,
  fromEditionKey: string,
  toEditionKey: string,
): Promise<CompareResult> {
  const q = new URLSearchParams({
    from_edition: fromEditionKey,
    to_edition: toEditionKey,
  })
  return api<CompareResult>(`/material/works/${workKey}/changes/?${q.toString()}`)
}

export async function fetchProviders(): Promise<Provider[]> {
  return api<Provider[]>(`/material/providers/`)
}

export async function fetchUserFollowedProviders(): Promise<UserProviderFollow[]> {
  return api<UserProviderFollow[]>(`/material/me/providers/`)
}

export async function followProvider(providerId: string, isPrimary = false): Promise<UserProviderFollow> {
  return api<UserProviderFollow>(`/material/me/providers/`, {
    method: 'POST',
    body: JSON.stringify({ provider_id: providerId, is_primary: isPrimary }),
  })
}

export async function unfollowProvider(userProviderId: string): Promise<void> {
  await api(`/material/me/providers/${userProviderId}/`, {
    method: 'DELETE',
  })
}

export async function fetchUserEdition(workKey: string): Promise<UserEditionSelection | null> {
  return api<UserEditionSelection | null>(`/material/me/editions/${workKey}/`)
}

export async function setUserEdition(workKey: string, editionKey: string): Promise<UserEditionSelection> {
  return api<UserEditionSelection>(`/material/me/editions/${workKey}/`, {
    method: 'POST',
    body: JSON.stringify({ edition_key: editionKey }),
  })
}

export async function dismissEditionBanner(workKey: string): Promise<void> {
  await api(`/material/me/editions/${workKey}/dismiss-banner/`, {
    method: 'POST',
  })
}

export async function reportMaterialItem(
  itemId: string,
  payload: MaterialReportPayload,
): Promise<{ id: string; status: string }> {
  return api<{ id: string; status: string }>(`/material/items/${itemId}/report/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchPublicSubjectMaterial(
  course: string,
  level: string,
  subject: string,
): Promise<{ works: Work[] }> {
  return api<{ works: Work[] }>(`/material/public/subjects/${course}/${level}/${subject}/material/`)
}
