import { Skeleton } from '@artha/design-system'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { currentUserId } from '~/lib/offline-queue'
import { useFeatureFlag } from '~/modules/observability'

import { DeleteNotesDialog } from '../components/DeleteNotesDialog'
import { UsageSection } from '../components/UsageSection'
import { useUsage } from '../hooks/useNotesQueries'
import { notesAnalytics } from '../lib/analytics'
import { deleteAll, exportAll } from '../lib/api'
import { notesKeys } from '../lib/keys'
import { clearNotesLocalData } from '../lib/local-data'
import { notify } from '../lib/notify'
import { NotesShell } from './NotesShell'
import { PdfSettingsContainer } from './PdfSettingsContainer'

/** Starts a download of `data` as a JSON file, from a Blob URL that is released right after. */
function download(data: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function Settings() {
  const qc = useQueryClient()
  const usage = useUsage()
  const pdfOn = useFeatureFlag('notes_pdf')
  const [exporting, setExporting] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteFailed, setDeleteFailed] = useState(false)

  const onExport = async () => {
    setExporting(true)
    notify.exportStarted()
    notesAnalytics.exportRequested()
    try {
      download(await exportAll(), 'artha-notes-export.json')
    } catch (error) {
      notify.error(error, 'Could not export your notes.')
    } finally {
      setExporting(false)
    }
  }

  const onDelete = async () => {
    setDeleting(true)
    setDeleteFailed(false)
    try {
      await deleteAll()
      const userId = await currentUserId()
      if (userId) await clearNotesLocalData(userId)
      qc.removeQueries({ queryKey: notesKeys.all })
      await qc.invalidateQueries()
      setConfirming(false)
      notify.allDeleted()
    } catch {
      setDeleteFailed(true)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <header className="space-y-1">
        <h1 className="font-display text-3xl font-extrabold">Notes settings</h1>
        <p className="text-muted-foreground">How much space your notes use, and your data.</p>
      </header>
      {usage.isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <UsageSection
          usage={usage.data}
          hideStorage={pdfOn}
          exporting={exporting}
          onExport={() => void onExport()}
          onDeleteAll={() => setConfirming(true)}
        />
      )}
      {pdfOn ? <PdfSettingsContainer /> : null}
      <DeleteNotesDialog
        open={confirming}
        onOpenChange={setConfirming}
        pending={deleting}
        failed={deleteFailed}
        onConfirm={() => void onDelete()}
      />
    </>
  )
}

export function NotesSettingsContainer() {
  return (
    <NotesShell width="max-w-3xl" allowWhenOff>
      <Settings />
    </NotesShell>
  )
}
