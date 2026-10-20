import { useMutation, useQueryClient } from '@tanstack/react-query'

import { bulkSetReviewed, fileCardReport, reviewCardOrQueue, saveCardOrQueue } from '../lib/api'
import { amendmentsKeys } from '../lib/keys'

export function useCardActions() {
  const qc = useQueryClient()

  const reviewMutation = useMutation({
    mutationFn: async ({ publicId, reviewed }: { publicId: string; reviewed: boolean }) => {
      await reviewCardOrQueue(publicId, reviewed)
      return { publicId, reviewed }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: amendmentsKeys.all })
    },
  })

  const saveMutation = useMutation({
    mutationFn: async ({ publicId, saved }: { publicId: string; saved: boolean }) => {
      await saveCardOrQueue(publicId, saved)
      return { publicId, saved }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: amendmentsKeys.all })
    },
  })

  const bulkReviewMutation = useMutation({
    mutationFn: async ({ publicIds, reviewed }: { publicIds: string[]; reviewed: boolean }) => {
      return bulkSetReviewed(publicIds, reviewed)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: amendmentsKeys.all })
    },
  })

  const reportMutation = useMutation({
    mutationFn: async ({ publicId, kind, message }: { publicId: string; kind: string; message: string }) => {
      return fileCardReport(publicId, kind, message)
    },
  })

  return {
    toggleReviewed: (publicId: string, currentReviewed: boolean) =>
      reviewMutation.mutateAsync({ publicId, reviewed: !currentReviewed }),
    toggleSaved: (publicId: string, currentSaved: boolean) =>
      saveMutation.mutateAsync({ publicId, saved: !currentSaved }),
    bulkReview: (publicIds: string[], reviewed: boolean) => bulkReviewMutation.mutateAsync({ publicIds, reviewed }),
    fileReport: (publicId: string, kind: string, message: string) =>
      reportMutation.mutateAsync({ publicId, kind, message }),
    isReviewing: reviewMutation.isPending,
    isSaving: saveMutation.isPending,
    isBulkReviewing: bulkReviewMutation.isPending,
    isReporting: reportMutation.isPending,
  }
}
