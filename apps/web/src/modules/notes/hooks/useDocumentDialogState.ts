import { useCallback, useMemo, useState } from 'react'

import type { DocumentSummary } from '../lib/document-types'
import type { DocumentQuotaDetails } from '../lib/errors'

/** Which document dialog is open and for which document. One at a time, by design: opening one closes the others. */
export interface DialogState {
  editId: string | null
  ocr: DocumentSummary | null
  exportDoc: DocumentSummary | null
  quota: DocumentQuotaDetails | null
}

const NONE: DialogState = { editId: null, ocr: null, exportDoc: null, quota: null }

export function useDocumentDialogState() {
  const [state, setState] = useState<DialogState>(NONE)
  const openEdit = useCallback((doc: Pick<DocumentSummary, 'id'>) => setState({ ...NONE, editId: doc.id }), [])
  const openOcr = useCallback((doc: DocumentSummary) => setState({ ...NONE, ocr: doc }), [])
  const openExport = useCallback((doc: DocumentSummary) => setState({ ...NONE, exportDoc: doc }), [])
  const openQuota = useCallback((quota: DocumentQuotaDetails) => setState({ ...NONE, quota }), [])
  const close = useCallback(() => setState(NONE), [])
  // One object that changes only when a dialog opens or closes, so a host holding it (the reader) does not re-render for nothing.
  return useMemo(
    () => ({ state, openEdit, openOcr, openExport, openQuota, close }),
    [state, openEdit, openOcr, openExport, openQuota, close],
  )
}

export type DocumentDialogs = ReturnType<typeof useDocumentDialogState>
