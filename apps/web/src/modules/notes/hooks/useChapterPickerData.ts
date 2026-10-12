import { ALL_CHAPTERS, useChapterCoverage, useSubjectCoverage } from '~/modules/coverage'

import type { PickerOption, PickerState } from '../lib/chapter-link'
import { useEnrolledSubjects, useLevelId } from './useNotesQueries'

/** The lists behind the chapter picker, read from My Coverage so a note is filed with the same keys the syllabus uses. */
export function useChapterPickerData(state: PickerState, options: { topics?: boolean } = {}) {
  const withTopics = options.topics ?? true
  const levelId = useLevelId()
  const subjects = useEnrolledSubjects()
  const chapterQuery = useSubjectCoverage(state.subjectId, state.subjectId !== '')
  const topicQuery = useChapterCoverage(
    state.chapterId,
    withTopics && state.chapterId !== '' && state.chapterId !== ALL_CHAPTERS,
  )
  const chapters: PickerOption[] =
    chapterQuery.data?.chapters.map((c) => ({ id: c.id, key: c.key, name: c.name })) ?? []
  const topics: PickerOption[] = topicQuery.data?.topics.map((t) => ({ id: t.id, key: t.key, name: t.name })) ?? []
  return {
    levelId,
    subjects: subjects.subjects as PickerOption[],
    chapters,
    topics,
    loadingSubjects: subjects.isPending,
    loadingChapters: chapterQuery.isLoading,
    loadingTopics: topicQuery.isLoading,
    failed: subjects.isError || chapterQuery.isError,
    retry: () => {
      void subjects.refetch()
      void chapterQuery.refetch()
    },
  }
}
