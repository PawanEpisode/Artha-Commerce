import { api, publicApi } from '~/lib/api'

import type { ChapterPyqItem, PaperFilterParams, PyqPaperCard, PyqPaperDetail } from './types'

export async function listPapers(params: PaperFilterParams = {}): Promise<PyqPaperCard[]> {
  const query = new URLSearchParams()
  if (params.course) query.set('course', params.course)
  if (params.level) query.set('level', params.level)
  if (params.subject) query.set('subject', params.subject)
  if (params.term) query.set('term', params.term)
  if (params.status) query.set('status', params.status)

  const qs = query.toString()
  const path = `/pyq/papers/${qs ? `?${qs}` : ''}`
  try {
    const res = await api<{ items: PyqPaperCard[] }>(path)
    return res.items
  } catch {
    const res = await publicApi<{ items: PyqPaperCard[] }>(path)
    return res?.items ?? []
  }
}

export async function getPaperDetail(idOrRef: string): Promise<PyqPaperDetail | null> {
  const path = `/pyq/papers/${idOrRef}/`
  try {
    return await api<PyqPaperDetail>(path)
  } catch {
    return await publicApi<PyqPaperDetail>(path)
  }
}

/**
 * Opens a PDF we host: adds it to the student's PDF library (once) and returns the document the reader opens, where they
 * can read, highlight and mark it. Needs sign-in and the PDF reader to be on for the student.
 */
export async function openHostedPaper(paperId: string, linkId: string): Promise<{ document_id: string }> {
  return await api<{ document_id: string }>(`/pyq/papers/${paperId}/links/${linkId}/open/`, { method: 'POST' })
}

export async function getChapterPyqs(
  chapterId: string,
  options?: { scheme_relation?: string },
): Promise<ChapterPyqItem[]> {
  const query = new URLSearchParams()
  if (options?.scheme_relation) query.set('scheme_relation', options.scheme_relation)

  const qs = query.toString()
  const path = `/pyq/chapters/${chapterId}/${qs ? `?${qs}` : ''}`
  try {
    const res = await api<{ items: ChapterPyqItem[] }>(path)
    return res.items
  } catch {
    const res = await publicApi<{ items: ChapterPyqItem[] }>(path)
    return res?.items ?? []
  }
}

export async function startPaperPractice(
  paperId: string,
  payload?: { mode?: 'untimed' | 'timed' },
): Promise<{ session_id: string }> {
  return await api<{ session_id: string }>(`/pyq/papers/${paperId}/practice/`, {
    method: 'POST',
    body: JSON.stringify(payload ?? { mode: 'untimed' }),
  })
}

export async function startChapterPractice(
  chapterId: string,
  payload?: { count?: number },
): Promise<{ session_id: string }> {
  return await api<{ session_id: string }>(`/pyq/chapters/${chapterId}/practice/`, {
    method: 'POST',
    body: JSON.stringify(payload ?? { count: 10 }),
  })
}
