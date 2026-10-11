import { ChapterRecallCard } from '../components/ChapterRecallCard'
import { useChapterStrength } from '../hooks/useChapterStrength'
import { showsStrength } from '../lib/chapterRecall'

/**
 * The recall section of a chapter page (My Coverage). Hidden when the `recall_system` flag is off, while it loads, and for a
 * chapter with no cards. Another module mounts it with the chapter id only: `<ChapterRecallSlot chapterId />`.
 */
export function ChapterRecallSlot({ chapterId }: { chapterId: string }) {
  const { enabled, data, isError, refetch } = useChapterStrength(chapterId)
  if (isError) {
    return enabled ? <ChapterRecallCard failed onRetry={() => void refetch()} /> : null
  }
  if (!showsStrength(enabled, data)) return null
  return <ChapterRecallCard strength={data} onRetry={() => void refetch()} />
}
