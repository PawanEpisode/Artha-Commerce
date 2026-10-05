import { api, publicApi } from '~/lib/api'

import type { ChapterSyllabus, CourseSummary, ExamTerm, LevelSyllabus, ReportNodeType, SubjectSyllabus } from './types'

const base = (course: string, level: string) => `/syllabus/courses/${course}/levels/${level}`

/** Server-safe. Null when the API has no such level, or is unreachable: callers fall back to the static catalog. */
export async function fetchLevel(course: string, level: string): Promise<LevelSyllabus | null> {
  try {
    return await publicApi<LevelSyllabus>(`${base(course, level)}/`)
  } catch {
    return null
  }
}

export async function fetchSubject(course: string, level: string, subject: string): Promise<SubjectSyllabus | null> {
  return publicApi<SubjectSyllabus>(`${base(course, level)}/subjects/${subject}/`)
}

export async function fetchChapter(
  course: string,
  level: string,
  subject: string,
  chapter: string,
): Promise<ChapterSyllabus | null> {
  return publicApi<ChapterSyllabus>(`${base(course, level)}/subjects/${subject}/chapters/${chapter}/`)
}

/** Public paths of every published subject and chapter, for the sitemap. Empty when the API is unreachable. */
export async function fetchSitemapPaths(): Promise<string[]> {
  try {
    const body = await publicApi<{ paths: string[] }>('/syllabus/sitemap/')
    return body?.paths ?? []
  } catch {
    return []
  }
}

export function reportSyllabusIssue(input: { node_type: ReportNodeType; node_id: string; message: string }) {
  return api<{ id: string; status: string }>('/syllabus/reports/', { method: 'POST', body: JSON.stringify(input) })
}

export async function fetchCourses(): Promise<CourseSummary[]> {
  return (await publicApi<CourseSummary[]>('/syllabus/courses/')) ?? []
}

export async function fetchTerms(course?: string, level?: string): Promise<ExamTerm[]> {
  const params = new URLSearchParams()
  if (course) params.set('course', course)
  if (level) params.set('level', level)
  const query = params.toString()
  return (await publicApi<ExamTerm[]>(`/syllabus/terms/${query ? `?${query}` : ''}`)) ?? []
}
