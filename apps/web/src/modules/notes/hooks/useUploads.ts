import { useSyncExternalStore } from 'react'

import { uploadManager } from '../lib/upload-client'
import { activeUploads, type UploadItem } from '../lib/upload-manager'

const NONE: readonly UploadItem[] = []

/** The tab's uploads (module-level store, so they survive route changes) and the actions on them. */
export function useUploads() {
  const items = useSyncExternalStore(uploadManager.subscribe, uploadManager.getSnapshot, () => NONE)
  return {
    items,
    active: activeUploads(items),
    start: uploadManager.start,
    retry: uploadManager.retry,
    cancel: uploadManager.cancel,
    dismiss: uploadManager.dismiss,
    keepBoth: uploadManager.keepBoth,
    discardDuplicate: uploadManager.discardDuplicate,
  }
}
