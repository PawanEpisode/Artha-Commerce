import { Alert, Button, Card, Skeleton } from '@artha/design-system'

import { PdfSettingsSection, PdfUsage } from '../components/library/PdfSettingsSection'
import { useDocumentDialogState } from '../hooks/useDocumentDialogState'
import { useUsage } from '../hooks/useNotesQueries'
import { useNotesSettings, useUpdateNotesSettings } from '../hooks/useNotesSettings'
import { fullQuota } from '../lib/upload-check'
import { ArchiveExportContainer } from './ArchiveExportContainer'
import { DocumentDialogs } from './DocumentDialogs'

/** The R2 part of the settings page (flag `notes_pdf`): reading and OCR preferences, PDF usage, and "Download my notes". */
export function PdfSettingsContainer() {
  const settings = useNotesSettings()
  const update = useUpdateNotesSettings()
  const usage = useUsage()
  const dialogs = useDocumentDialogState()

  const manageStorage = () => {
    const data = usage.data
    if (!data) return
    dialogs.openQuota(
      fullQuota(data) ?? {
        kind: 'storage',
        used: data.used.storage_bytes,
        limit: (data.limits.max_storage_mb ?? 0) * 1024 * 1024,
        plan: data.plan,
        largest_documents: data.largest_documents,
      },
    )
  }

  return (
    <>
      {settings.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : settings.isError || !settings.data ? (
        <Alert variant="error">
          <span className="flex flex-wrap items-center gap-3">
            <span>We could not load your PDF settings.</span>
            <Button size="sm" variant="outline" onClick={() => void settings.refetch()}>
              Try again
            </Button>
          </span>
        </Alert>
      ) : (
        <PdfSettingsSection
          settings={settings.data}
          saving={update.isPending}
          onChange={(patch) => update.mutate(patch)}
        />
      )}
      {update.isError ? <Alert variant="error">Your last change was not saved. Please try again.</Alert> : null}
      {usage.data ? <PdfUsage usage={usage.data} onManageStorage={manageStorage} /> : null}
      <Card className="space-y-3 p-6">
        <h2 className="font-display text-xl font-bold">Download my notes</h2>
        <ArchiveExportContainer />
      </Card>
      <DocumentDialogs controller={dialogs} />
    </>
  )
}
