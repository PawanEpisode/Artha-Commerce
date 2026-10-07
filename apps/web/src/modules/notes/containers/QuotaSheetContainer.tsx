import { useState } from 'react'

import { DeleteDocumentDialog } from '../components/library/DeleteDocumentDialog'
import { type LargestDocument, QuotaSheet } from '../components/library/QuotaSheet'
import { useDocumentActions } from '../hooks/useLibrary'
import { useUsage } from '../hooks/useNotesQueries'
import { getDocument } from '../lib/documents-api'
import { openSignedUrl } from '../lib/download'
import type { DocumentQuotaDetails } from '../lib/errors'
import { notifyDocs } from '../lib/notify-documents'

interface QuotaSheetContainerProps {
  quota: DocumentQuotaDetails | null
  onOpenChange: (open: boolean) => void
  showLibraryLink?: boolean
}

/**
 * The quota sheet with its actions: the five largest PDFs (from the server's refusal, or `usage`) with Open, Download
 * original (a freshly signed link) and Delete (permanent, confirmed, and it says how much space it frees).
 */
export function QuotaSheetContainer({ quota, onOpenChange, showLibraryLink }: QuotaSheetContainerProps) {
  const usage = useUsage()
  const actions = useDocumentActions()
  const [busyId, setBusyId] = useState<string>()
  const [deleting, setDeleting] = useState<LargestDocument | null>(null)
  const [pending, setPending] = useState(false)
  const largest = quota?.largest_documents ?? usage.data?.largest_documents ?? []

  const download = async (doc: LargestDocument) => {
    setBusyId(doc.id)
    try {
      const detail = await getDocument(doc.id)
      if (detail.file_url) openSignedUrl(detail.file_url, detail.original_filename)
      else notifyDocs.error(undefined, 'This PDF is not available to download yet.')
    } catch (error) {
      notifyDocs.error(error, 'Could not download the PDF.')
    } finally {
      setBusyId(undefined)
    }
  }

  const confirmDelete = async () => {
    if (!deleting) return
    setPending(true)
    const ok = await actions.purge(deleting)
    setPending(false)
    if (ok) {
      setDeleting(null)
      onOpenChange(false)
    }
  }

  return (
    <>
      <QuotaSheet
        open={quota !== null}
        onOpenChange={onOpenChange}
        quota={quota}
        largest={largest}
        resetsOn={usage.data?.resets_on}
        busyId={busyId}
        onDownload={(doc) => void download(doc)}
        onDelete={setDeleting}
        showLibraryLink={showLibraryLink}
      />
      <DeleteDocumentDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        doc={deleting}
        busy={pending}
        onConfirm={() => void confirmDelete()}
      />
    </>
  )
}
