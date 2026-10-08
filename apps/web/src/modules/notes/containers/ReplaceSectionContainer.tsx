import { useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { useOnline } from '~/modules/personalization'

import { AttentionSheet } from '../components/replace/AttentionSheet'
import { ReplaceSection } from '../components/replace/ReplaceSection'
import { useAttention, useResolveAttention } from '../hooks/useReplace'
import type { DocumentDetail } from '../lib/document-types'
import type { DocumentQuotaDetails } from '../lib/errors'
import { notifyDocs } from '../lib/notify-documents'
import { isReplaceActive, openCount, replaceStatusText } from '../lib/replace-copy'
import type { AttentionAction, AttentionItem } from '../lib/replace-types'
import { QuotaSheetContainer } from './QuotaSheetContainer'
import { UploadSheetContainer } from './UploadSheetContainer'

/**
 * Replace edition in the document details (flag `notes_ai`, fails closed): a newer file for this document, and for a document
 * that IS a newer edition, where its marks went and the ones that wait for the student.
 */
export function ReplaceSectionContainer({ doc }: { doc: DocumentDetail }) {
  const flag = useFeatureFlag('notes_ai', { strict: true })
  const online = useOnline()
  const isReplacement = doc.replaces_document_id !== null
  const attention = useAttention(doc.id, flag && isReplacement)
  const resolve = useResolveAttention(doc.id)
  const [reviewing, setReviewing] = useState(false)
  const [replacing, setReplacing] = useState(false)
  const [quota, setQuota] = useState<DocumentQuotaDetails | null>(null)
  const [busyId, setBusyId] = useState<string>()
  if (!flag) return null

  const view = {
    reanchor_status: attention.data?.status ?? doc.reanchor_status,
    reanchor: attention.data?.stats ?? doc.reanchor,
  }
  const items = attention.data?.items ?? []
  const pending = openCount(items)

  const decide = (item: AttentionItem, action: AttentionAction) => {
    setBusyId(item.id)
    resolve.mutate(
      { itemId: item.id, action },
      {
        onError: (error) => notifyDocs.error(error, 'Could not save that decision.'),
        onSettled: () => setBusyId(undefined),
      },
    )
  }

  return (
    <>
      <ReplaceSection
        statusText={isReplacement ? replaceStatusText(view) : null}
        working={isReplaceActive(view)}
        openCount={pending}
        canReplace={doc.status === 'ready' && !doc.deleted_at}
        online={online}
        onReview={() => setReviewing(true)}
        onReplace={() => setReplacing(true)}
      />
      <AttentionSheet
        open={reviewing}
        onOpenChange={setReviewing}
        title={doc.title}
        items={items}
        loading={attention.isPending && attention.fetchStatus !== 'idle'}
        failed={attention.isError}
        busyId={busyId}
        online={online}
        onRetry={() => void attention.refetch()}
        onResolve={decide}
      />
      <UploadSheetContainer
        open={replacing}
        onOpenChange={setReplacing}
        replace={{ docId: doc.id, title: doc.title }}
        onQuota={(details) => {
          setReplacing(false)
          setQuota(details)
        }}
      />
      <QuotaSheetContainer quota={quota} onOpenChange={(open) => !open && setQuota(null)} />
    </>
  )
}
