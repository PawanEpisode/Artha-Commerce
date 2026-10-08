import { useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { useOnline } from '~/modules/personalization'

import { UnlockSection } from '../components/replace/UnlockSection'
import { useUnlock, useUnlockWatch } from '../hooks/useUnlock'
import type { DocumentDetail } from '../lib/document-types'
import { canUnlock, isUnlocking, unlockErrorText, unlockStatusText } from '../lib/unlock-copy'

/** Unlock for search in the document details (flag `notes_ai`, fails closed): only for a PDF that is waiting for its password. */
export function UnlockSectionContainer({ doc }: { doc: DocumentDetail }) {
  const flag = useFeatureFlag('notes_ai', { strict: true })
  const online = useOnline()
  const send = useUnlock(doc.id)
  const [error, setError] = useState<string>()
  const watched = useUnlockWatch(doc.id, flag && isUnlocking(doc))
  if (!flag) return null
  const current = watched.data ?? doc
  const relevant = current.status === 'needs_password' || current.unlock_status !== 'none'
  if (!relevant) return null

  return (
    <UnlockSection
      statusText={unlockStatusText(current)}
      working={isUnlocking(current) || send.isPending}
      canUnlock={canUnlock(current) && !send.isPending}
      online={online}
      error={error}
      onSubmit={(password) => {
        setError(undefined)
        send.mutate(password, { onError: (e) => setError(unlockErrorText(e)) })
      }}
    />
  )
}
