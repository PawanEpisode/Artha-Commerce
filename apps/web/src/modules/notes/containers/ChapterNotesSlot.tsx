import { useFeatureFlag } from '~/modules/observability'

import { ChapterNotesCard } from '../components/ChapterNotesCard'
import { useChapterNotesOverview, useLevelId } from '../hooks/useNotesQueries'
import { isFeatureDisabled } from '../lib/errors'

/**
 * The notes section of a chapter page (My Coverage). Hidden when the `notes` flag is off, on the web or the server.
 * Another module mounts it with stable keys only: `<ChapterNotesSlot subjectKey chapterKey />`.
 */
export function ChapterNotesSlot({ subjectKey, chapterKey }: { subjectKey: string; chapterKey: string }) {
  const enabled = useFeatureFlag('notes')
  const levelId = useLevelId()
  const overview = useChapterNotesOverview(subjectKey, chapterKey, enabled)
  if (!enabled || isFeatureDisabled(overview.error)) return null
  return (
    <ChapterNotesCard
      state={overview.isError ? 'error' : overview.data ? 'ready' : 'loading'}
      overview={overview.data}
      subjectKey={subjectKey}
      chapterKey={chapterKey}
      levelId={levelId}
      onRetry={() => void overview.refetch()}
    />
  )
}
