import { useRouterState } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { UploadProgressChip } from '../components/library/UploadProgressChip'
import { useUploadEffects } from '../hooks/useUploadEffects'
import { useUploadRowActions } from '../hooks/useUploadRowActions'
import { useUploads } from '../hooks/useUploads'
import type { DocumentQuotaDetails } from '../lib/errors'
import { announceChange } from '../lib/upload-announce'
import type { UploadItem } from '../lib/upload-manager'
import { QuotaSheetContainer } from './QuotaSheetContainer'

/** A finished upload leaves the chip after this long (the toast already offered Open). */
const READY_LINGER_MS = 8000

/** The sentence for the live region: the most recent change worth saying. */
function useAnnouncement(items: readonly UploadItem[]) {
  const seen = useRef(new Map<string, UploadItem>())
  const [text, setText] = useState('')
  useEffect(() => {
    for (const item of items) {
      const message = announceChange(seen.current.get(item.id), item)
      if (message) setText(message)
      seen.current.set(item.id, item)
    }
  }, [items])
  return text
}

/**
 * Mounted once in the `/app` layout. Shows the compact upload chip on every screen except the library (which draws the same
 * rows inline), runs the upload effects, and hosts the quota sheet a failed upload can open. Renders nothing visible when no
 * upload exists.
 */
export function UploadProgressContainer() {
  const { items, dismiss } = useUploads()
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const [quota, setQuota] = useState<DocumentQuotaDetails | null>(null)
  const actions = useUploadRowActions(setQuota)
  const announcement = useAnnouncement(items)
  useUploadEffects()

  useEffect(() => {
    const timers = items.filter((i) => i.phase === 'ready').map((i) => setTimeout(() => dismiss(i.id), READY_LINGER_MS))
    return () => timers.forEach(clearTimeout)
  }, [items, dismiss])

  return (
    <>
      <UploadProgressChip
        items={items}
        announcement={announcement}
        hidden={pathname.startsWith('/app/notes/library')}
        {...actions}
      />
      {/* Mounted only when needed: it reads usage, and the layout must not ask for that on every screen. */}
      {quota ? <QuotaSheetContainer quota={quota} onOpenChange={(open) => !open && setQuota(null)} /> : null}
    </>
  )
}
