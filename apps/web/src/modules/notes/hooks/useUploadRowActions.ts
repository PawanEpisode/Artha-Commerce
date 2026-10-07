import { useNavigate } from '@tanstack/react-router'

import type { UploadRowActions } from '../components/library/UploadRow'
import type { DocumentQuotaDetails } from '../lib/errors'
import { useDocumentActions } from './useLibrary'
import { useUploads } from './useUploads'

/** The actions of an upload row (cancel, retry, dismiss, duplicate choices, manage storage), the same wherever it is shown. */
export function useUploadRowActions(onQuota: (details: DocumentQuotaDetails) => void): UploadRowActions {
  const uploads = useUploads()
  const navigate = useNavigate()
  const { refresh } = useDocumentActions()
  return {
    onCancel: uploads.cancel,
    onRetry: uploads.retry,
    onDismiss: uploads.dismiss,
    onKeepBoth: uploads.keepBoth,
    onOpenExisting: (item) => {
      const existing = item.duplicateOf
      void uploads.discardDuplicate(item.id).then(async () => {
        await refresh()
        if (existing) await navigate({ to: '/app/notes/pdf/$docId', params: { docId: existing } })
      })
    },
    onManageStorage: (item) => item.failure?.quota && onQuota(item.failure.quota),
  }
}
