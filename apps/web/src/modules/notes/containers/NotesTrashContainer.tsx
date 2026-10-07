import { Alert, Button, EmptyState, Skeleton, Trash2 } from '@artha/design-system'
import { useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { useOnline } from '~/modules/personalization'

import { DeleteDocumentDialog } from '../components/library/DeleteDocumentDialog'
import { TrashedDocuments } from '../components/library/TrashedDocuments'
import { TrashList } from '../components/TrashList'
import { flattenDocuments, useDocumentActions, useDocumentList } from '../hooks/useLibrary'
import { useNoteActions } from '../hooks/useNoteActions'
import { flattenPages, useNoteList } from '../hooks/useNotesQueries'
import type { DocumentSummary } from '../lib/document-types'
import { NotesShell } from './NotesShell'

function Trash() {
  const online = useOnline()
  const actions = useNoteActions()
  const list = useNoteList({ trashed: true, limit: 30 })
  const { items } = flattenPages(list.data?.pages)
  const [restoringId, setRestoringId] = useState<string>()
  const pdfOn = useFeatureFlag('notes_pdf')
  const docActions = useDocumentActions()
  const docs = useDocumentList({ trashed: true, limit: 30 }, pdfOn)
  const trashedDocs = flattenDocuments(docs.data?.pages)
  const [busyDocId, setBusyDocId] = useState<string>()
  const [purging, setPurging] = useState<DocumentSummary | null>(null)
  const [purgeBusy, setPurgeBusy] = useState(false)
  const showDocs = pdfOn && !docs.isError && trashedDocs.length > 0

  return (
    <>
      <header className="space-y-1">
        <h1 className="font-display text-3xl font-extrabold">Trash</h1>
        <p className="text-muted-foreground">Deleted notes stay here for 30 days, then they are removed for good.</p>
      </header>
      {list.isPending ? (
        <div aria-busy="true" className="space-y-3">
          <span role="status" className="sr-only">
            Loading the trash…
          </span>
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : list.isError ? (
        <Alert variant="error">
          <span className="flex flex-wrap items-center gap-3">
            <span>We could not load the trash.</span>
            <Button size="sm" variant="outline" onClick={() => void list.refetch()}>
              Try again
            </Button>
          </span>
        </Alert>
      ) : items.length === 0 && !showDocs ? (
        <EmptyState
          icon={<Trash2 aria-hidden />}
          title="The trash is empty"
          description="Notes you delete will wait here for 30 days."
        />
      ) : (
        <div className="space-y-6">
          {!online ? (
            <Alert variant="info">
              <span>You are offline. You can restore notes when you are back online.</span>
            </Alert>
          ) : null}
          {items.length > 0 ? (
            <section aria-labelledby="trash-notes-h" className="space-y-3">
              {showDocs ? (
                <h2 id="trash-notes-h" className="font-display text-xl font-bold">
                  Notes
                </h2>
              ) : null}
              <TrashList
                items={items}
                online={online}
                restoringId={restoringId}
                onRestore={async (note) => {
                  setRestoringId(note.id)
                  await actions.restore(note)
                  setRestoringId(undefined)
                }}
              />
              {list.hasNextPage ? (
                <Button variant="outline" disabled={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
                  {list.isFetchingNextPage ? 'Loading…' : 'Load more'}
                </Button>
              ) : null}
            </section>
          ) : null}
          {showDocs ? (
            <section aria-labelledby="trash-docs-h" className="space-y-3">
              <h2 id="trash-docs-h" className="font-display text-xl font-bold">
                PDFs
              </h2>
              <TrashedDocuments
                items={trashedDocs}
                online={online}
                busyId={busyDocId}
                onRestore={async (doc) => {
                  setBusyDocId(doc.id)
                  await docActions.restore(doc)
                  setBusyDocId(undefined)
                }}
                onDeleteNow={setPurging}
              />
              {docs.hasNextPage ? (
                <Button variant="outline" disabled={docs.isFetchingNextPage} onClick={() => void docs.fetchNextPage()}>
                  {docs.isFetchingNextPage ? 'Loading…' : 'Load more PDFs'}
                </Button>
              ) : null}
            </section>
          ) : null}
        </div>
      )}
      <DeleteDocumentDialog
        open={purging !== null}
        onOpenChange={(open) => !open && setPurging(null)}
        doc={purging}
        busy={purgeBusy}
        onConfirm={async () => {
          if (!purging) return
          setPurgeBusy(true)
          const ok = await docActions.purge(purging)
          setPurgeBusy(false)
          if (ok) setPurging(null)
        }}
      />
    </>
  )
}

export function NotesTrashContainer() {
  return (
    <NotesShell width="max-w-3xl">
      <Trash />
    </NotesShell>
  )
}
