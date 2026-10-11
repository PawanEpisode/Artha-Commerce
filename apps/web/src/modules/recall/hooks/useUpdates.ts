import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { trackRecall } from '../lib/analytics'
import { recallApi } from '../lib/api'
import { recallKeys } from '../lib/keys'
import { kindsIn } from '../lib/updates'

/** The update preview is read only; it loads when the sheet opens. */
export const useUpdatePreview = (subscriptionId: string, enabled: boolean) =>
  useQuery({
    queryKey: recallKeys.updatePreview(subscriptionId),
    queryFn: async () => {
      const p = await recallApi.updatePreview(subscriptionId)
      trackRecall('recall_update_previewed', {
        changes: p.counts.total ?? 0,
        kinds_present: kindsIn(p.counts).length,
      })
      return p
    },
    enabled,
    staleTime: 0,
  })

/** A change of version reaches cards, today and stats, so everything under `recall` is refetched. */
function useRefresh() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: recallKeys.all })
}

export function useApplyUpdate(subscriptionId: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: () => recallApi.applyUpdate(subscriptionId),
    onSuccess: (r) => {
      trackRecall('recall_update_applied', {
        changes: r.result.added + r.result.removed + r.result.silent + r.result.rechecked,
        recheck: r.result.rechecked,
      })
      void refresh()
    },
  })
}

export function useSetFollow(subscriptionId: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (follow: boolean) => recallApi.setFollow(subscriptionId, follow),
    onSuccess: (_r, follow) => {
      trackRecall('recall_follow_toggled', { follow })
      void refresh()
    },
  })
}

export const useChapterRemaps = () => useQuery({ queryKey: recallKeys.chapterRemaps, queryFn: recallApi.chapterRemaps })

export function useChooseChapter() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (v: { remapId: string; chapterId: string; relation: string }) =>
      recallApi.chooseChapter(v.remapId, v.chapterId),
    onSuccess: (_r, v) => {
      trackRecall('recall_chapter_remap_chosen', { relation: v.relation })
      void refresh()
    },
  })
}
