import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'

import { useChosenSubjects } from '~/modules/coverage'
import { fetchCourses, fetchLevel, fetchSubject } from '~/modules/syllabus'

import type { StudentPapers } from '../lib/studentPapers'

const STALE = 10 * 60_000

/** The syllabus is public and slow to change, so each step is fetched once and kept for a while. */
export function useCourses() {
  return useQuery({ queryKey: ['recall', 'syllabus', 'courses'], queryFn: fetchCourses, staleTime: STALE })
}

export function useLevelSubjects(course: string, level: string) {
  return useQuery({
    queryKey: ['recall', 'syllabus', 'level', course, level],
    queryFn: async () => {
      const l = await fetchLevel(course, level)
      if (!l) throw new Error('level not found')
      return l.subjects
    },
    enabled: Boolean(course && level),
    staleTime: STALE,
  })
}

export function useSubjectChapters(course: string, level: string, subject: string) {
  return useQuery({
    queryKey: ['recall', 'syllabus', 'subject', course, level, subject],
    queryFn: async () => {
      const s = await fetchSubject(course, level, subject)
      if (!s) throw new Error('subject not found')
      return s.chapters
    },
    enabled: Boolean(course && level && subject),
    staleTime: STALE,
  })
}

/** The student's own papers (core plus chosen electives) and her enrolment's course and level, or null without one. */
export function useStudentPapers(): StudentPapers | null {
  const { data, subjects } = useChosenSubjects()
  return useMemo(
    () =>
      data
        ? {
            course: data.enrollment.course.code,
            level: data.enrollment.level.code,
            keys: new Set(subjects.map((s) => s.key)),
          }
        : null,
    [data, subjects],
  )
}
