import { api, publicApi } from '~/lib/api'

import type {
  AdaptiveStartPayload,
  ChapterDetailData,
  ChapterTile,
  ExternalLogPayload,
  McqFilter,
  McqHomeData,
  McqSetCard,
  McqSetDetail,
  StartQuickPracticePayload,
} from './types'

export async function getMcqHome(): Promise<McqHomeData> {
  return await api<McqHomeData>('/mcq/home/')
}

export async function getSubjectTiles(
  subjectKey: string,
  params?: { course?: string; level?: string },
): Promise<ChapterTile[]> {
  const query = new URLSearchParams()
  if (params?.course) query.set('course', params.course)
  if (params?.level) query.set('level', params.level)

  const qs = query.toString()
  const path = `/mcq/subjects/${subjectKey}/tiles/${qs ? `?${qs}` : ''}`
  const res = await api<{ items: ChapterTile[] }>(path)
  return res.items
}

export async function getChapterDetail(
  subjectKey: string,
  chapterKey: string,
  params?: { course?: string; level?: string },
): Promise<ChapterDetailData | null> {
  const query = new URLSearchParams()
  if (params?.course) query.set('course', params.course)
  if (params?.level) query.set('level', params.level)

  const qs = query.toString()
  const path = `/mcq/subjects/${subjectKey}/chapters/${chapterKey}/${qs ? `?${qs}` : ''}`
  return await api<ChapterDetailData>(path)
}

export async function listMcqSets(filter: McqFilter = {}): Promise<McqSetCard[]> {
  const query = new URLSearchParams()
  if (filter.subject) query.set('subject', filter.subject)
  if (filter.chapter) query.set('chapter', filter.chapter)
  if (filter.kind) query.set('kind', filter.kind)
  if (filter.term) query.set('term', filter.term)
  if (filter.delivery) query.set('delivery', filter.delivery)

  const qs = query.toString()
  const path = `/mcq/sets/${qs ? `?${qs}` : ''}`
  try {
    const res = await api<{ items: McqSetCard[] }>(path)
    return res.items
  } catch {
    const res = await publicApi<{ items: McqSetCard[] }>(path)
    return res?.items ?? []
  }
}

export async function getMcqSet(slug: string): Promise<McqSetDetail | null> {
  const path = `/mcq/sets/${slug}/`
  try {
    return await api<McqSetDetail>(path)
  } catch {
    return await publicApi<McqSetDetail>(path)
  }
}

export async function startQuickPractice(payload: StartQuickPracticePayload): Promise<{ session_id: string }> {
  return await api<{ session_id: string }>('/mcq/quick-start/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function startSetPractice(
  slug: string,
  mode: 'untimed' | 'timed' = 'untimed',
): Promise<{ session_id: string }> {
  return await api<{ session_id: string }>(`/mcq/sets/${slug}/start/`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  })
}

export async function recordSetClick(slug: string): Promise<{ outbound_url: string }> {
  return await api<{ outbound_url: string }>(`/mcq/sets/${slug}/click/`, {
    method: 'POST',
  })
}

export async function logExternalScore(payload: ExternalLogPayload): Promise<{ id: string; percentage: number }> {
  return await api<{ id: string; percentage: number }>('/mcq/external-logs/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function startAdaptiveSession(
  payload: AdaptiveStartPayload,
): Promise<{ run_id: string; session_id: string; round: number }> {
  return await api<{ run_id: string; session_id: string; round: number }>('/mcq/adaptive/start/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
