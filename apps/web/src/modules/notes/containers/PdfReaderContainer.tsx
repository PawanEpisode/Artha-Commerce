import { ArrowLeft, Button, Container, EmptyState, Notebook } from '@artha/design-system'

import { useFeatureFlag } from '~/modules/observability'

import { ReaderErrorState } from '../components/reader/ReaderErrorState'
import { ReaderLoading } from '../components/reader/ReaderLoading'
import { useDocument, useDocumentProcessing, useRefreshFileUrl } from '../hooks/useDocuments'
import { isFeatureDisabled, isNotFound, requestIdOf } from '../lib/errors'
import type { PdfEngine } from '../lib/pdf-engine'
import type { ReaderSearch } from '../lib/reader-schema'
import { openability } from '../lib/reader-state'
import type { ReaderExtensions } from './reader-extensions'
import { ReaderSession } from './ReaderSession'

export interface PdfReaderContainerProps {
  docId: string
  /** The validated URL search (`readerSearchSchema`). */
  search: ReaderSearch
  /** Merges a patch into the URL search, replacing the history entry. */
  onSearchChange: (patch: Partial<ReaderSearch>) => void
  /** Back to where the student came from (the library when there is no history). */
  onBack: () => void
  /** Plug-ins for the annotation layer and the library (see `ReaderExtensions`). */
  extensions?: ReaderExtensions
  onMakeSearchable?: () => void
  /** Test seam: replaces pdf.js. */
  engine?: PdfEngine
}

/**
 * `/app/notes/pdf/$docId`. Loads the document record and decides what to show: the flag-off state, a missing document,
 * "still preparing" (polling until the file is clean), a rejected file, or the reader itself.
 */
export function PdfReaderContainer({
  docId,
  search,
  onSearchChange,
  onBack,
  extensions,
  onMakeSearchable,
  engine,
}: PdfReaderContainerProps) {
  const enabled = useFeatureFlag('notes_pdf')
  const query = useDocument(docId)
  const refreshUrl = useRefreshFileUrl(docId)
  const doc = query.data
  const state = doc ? openability(doc) : null
  // While the server prepares the file, poll; the document is refetched when the status changes.
  useDocumentProcessing(docId, state?.kind === 'preparing')

  const off = !enabled || isFeatureDisabled(query.error)

  if (off)
    return (
      <Container className="grid min-h-dvh max-w-lg place-items-center py-12">
        <EmptyState
          icon={<Notebook aria-hidden />}
          title="The PDF reader is not available yet"
          description="We are rolling it out gradually. Your typed notes are not affected."
          action={
            <Button variant="outline" onClick={onBack}>
              <ArrowLeft aria-hidden />
              Back to my notes
            </Button>
          }
        />
      </Container>
    )

  if (query.isError) {
    if (isNotFound(query.error))
      return (
        <ReaderErrorState
          title="We could not find this document"
          message="It may have been deleted, or it belongs to another account."
          onBack={onBack}
        />
      )
    return (
      <ReaderErrorState
        message="We could not load this document. Check your connection and try again."
        requestId={requestIdOf(query.error)}
        onRetry={() => void query.refetch()}
        onBack={onBack}
      />
    )
  }

  if (!doc || !state) return <ReaderLoading />

  if (state.kind === 'preparing')
    return (
      <ReaderErrorState
        variant="info"
        title="Getting your PDF ready"
        message="We are checking the file. It opens here as soon as it is ready."
        onRetry={() => void query.refetch()}
        onBack={onBack}
      />
    )

  if (state.kind === 'unavailable')
    return <ReaderErrorState title={state.title} message={state.message} onBack={onBack} />

  return (
    <ReaderSession
      key={doc.id}
      doc={doc}
      search={search}
      onSearchChange={onSearchChange}
      onBack={onBack}
      refreshUrl={refreshUrl}
      engine={engine}
      extensions={extensions}
      onMakeSearchable={onMakeSearchable}
    />
  )
}
