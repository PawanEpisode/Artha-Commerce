import { useQuery } from '@tanstack/react-query'

import { recallApi } from '../lib/api'
import { recallKeys } from '../lib/keys'
import { useRecallEnabled } from './useRecallBasics'

/**
 * Recall strength of one chapter, for the chapter page. Only asked when the `recall_system` flag is on for her. A review that
 * syncs invalidates it (`useSync`), so the card follows what she just did. A failure never throws: the card shows its own
 * retry (a 403 `feature_disabled` is simply "hidden").
 */
export function useChapterStrength(chapterId: string) {
  const enabled = useRecallEnabled()
  const query = useQuery({
    queryKey: recallKeys.chapterStrength(chapterId),
    queryFn: () => recallApi.chapterStrength(chapterId),
    enabled,
    staleTime: 30_000,
    retry: false,
  })
  return { enabled, ...query }
}
