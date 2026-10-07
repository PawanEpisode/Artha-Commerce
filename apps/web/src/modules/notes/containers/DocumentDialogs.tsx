import type { DocumentDialogs as Controller } from '../hooks/useDocumentDialogState'
import { DocumentDetailsContainer } from './DocumentDetailsContainer'
import { ExportDialogContainer } from './ExportDialogContainer'
import { OcrDialogContainer } from './OcrDialogContainer'
import { QuotaSheetContainer } from './QuotaSheetContainer'

/** The document dialogs of a screen, driven by `useDocumentDialogState`: details, OCR, export and the quota sheet. */
export function DocumentDialogs({
  controller,
  showLibraryLink,
}: {
  controller: Controller
  showLibraryLink?: boolean
}) {
  const { state, close, openQuota } = controller
  return (
    <>
      {state.editId ? <DocumentDetailsContainer docId={state.editId} open onOpenChange={(o) => !o && close()} /> : null}
      {state.ocr ? (
        <OcrDialogContainer doc={state.ocr} open onOpenChange={(o) => !o && close()} onQuota={openQuota} />
      ) : null}
      {state.exportDoc ? (
        <ExportDialogContainer doc={state.exportDoc} open onOpenChange={(o) => !o && close()} onQuota={openQuota} />
      ) : null}
      {state.quota ? (
        <QuotaSheetContainer
          quota={state.quota}
          onOpenChange={(o) => !o && close()}
          showLibraryLink={showLibraryLink}
        />
      ) : null}
    </>
  )
}
