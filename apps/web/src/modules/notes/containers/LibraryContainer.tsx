import { EmptyState, Notebook } from '@artha/design-system'
import { useNavigate } from '@tanstack/react-router'
import { useCallback, useMemo, useState } from 'react'

import { useSubjectCoverage } from '~/modules/coverage'
import { useFeatureFlag } from '~/modules/observability'
import { useOnline } from '~/modules/personalization'

import { DocumentCard } from '../components/library/DocumentCard'
import { LibraryFilters } from '../components/library/LibraryFilters'
import { LibraryView } from '../components/library/LibraryView'
import { UploadRow } from '../components/library/UploadRow'
import { useDocumentDialogState } from '../hooks/useDocumentDialogState'
import { flattenDocuments, useDocumentActions, useDocumentList } from '../hooks/useLibrary'
import { useEnrolledSubjects, useLevelId, useTags, useUsage } from '../hooks/useNotesQueries'
import { useOcrTransitions } from '../hooks/useOcrTransitions'
import { useUploadRowActions } from '../hooks/useUploadRowActions'
import { useUploads } from '../hooks/useUploads'
import { getDocument } from '../lib/documents-api'
import { openSignedUrl } from '../lib/download'
import { isFeatureDisabled, requestIdOf } from '../lib/errors'
import { activeLibraryFilters, libraryListParams, type LibrarySearch } from '../lib/library-schema'
import { notifyDocs } from '../lib/notify-documents'
import { fullQuota, limitsFromUsage } from '../lib/upload-check'
import { DocumentDialogs } from './DocumentDialogs'
import { NotesShell } from './NotesShell'
import { UploadSheetContainer } from './UploadSheetContainer'

function Library({ search }: { search: LibrarySearch }) {
  const navigate = useNavigate()
  const online = useOnline()
  const levelId = useLevelId()
  const enabled = useFeatureFlag('notes_pdf')
  const { subjects } = useEnrolledSubjects()
  const subjectId = subjects.find((s) => s.key === search.subject)?.id ?? ''
  const chapters = useSubjectCoverage(subjectId, subjectId !== '')
  const tags = useTags()
  const usage = useUsage()
  const uploads = useUploads()
  const dialogs = useDocumentDialogState()
  const actions = useDocumentActions()
  const rowActions = useUploadRowActions(dialogs.openQuota)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [dropped, setDropped] = useState<File[] | null>(null)

  const waitingForLevel = Boolean(search.subject) && levelId === undefined
  const list = useDocumentList(libraryListParams(search, levelId), enabled && !waitingForLevel)
  const items = flattenDocuments(list.data?.pages)
  const ocrEntries = useMemo(
    () => items.map((d) => ({ id: d.id, status: d.ocr_status, pages: d.ocr_pages_total || d.page_count || 0 })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [list.data],
  )
  const openDocument = useCallback(
    (id: string) => void navigate({ to: '/app/notes/pdf/$docId', params: { docId: id } }),
    [navigate],
  )
  useOcrTransitions(ocrEntries, openDocument)
  const limits = limitsFromUsage(usage.data)

  if (!enabled || isFeatureDisabled(list.error)) {
    return (
      <EmptyState
        icon={<Notebook aria-hidden />}
        title="The PDF library is not available yet"
        description="We are rolling it out gradually. Your typed notes are not affected."
      />
    )
  }

  const go = (next: LibrarySearch) => void navigate({ to: '/app/notes/library', search: next, replace: true })
  const onUpload = () => {
    const blocked = fullQuota(usage.data)
    if (blocked) dialogs.openQuota(blocked)
    else setSheetOpen(true)
  }
  const download = async (id: string) => {
    try {
      const detail = await getDocument(id)
      if (detail.file_url) openSignedUrl(detail.file_url, detail.original_filename)
    } catch (error) {
      notifyDocs.error(error, 'Could not download the PDF.')
    }
  }

  const visibleUploads = uploads.items.filter((u) => u.phase !== 'ready')
  const state = list.isPending && !waitingForLevel ? 'loading' : list.isError ? 'error' : 'ready'

  return (
    <>
      <LibraryView
        state={state}
        items={items}
        filtered={activeLibraryFilters(search).length > 0}
        usage={usage.data}
        limits={limits}
        online={online}
        requestId={requestIdOf(list.error)}
        hasUploads={visibleUploads.length > 0}
        filters={
          <LibraryFilters
            search={search}
            subjects={subjects.map((s) => ({ value: s.key, label: s.name }))}
            chapters={(chapters.data?.chapters ?? []).map((c) => ({ value: c.key, label: c.name }))}
            tags={tags.data ?? []}
            onChange={go}
          />
        }
        uploads={
          visibleUploads.length > 0 ? (
            <ul aria-label="Uploads in progress" className="space-y-2">
              {visibleUploads.map((item) => (
                <li key={item.id}>
                  <UploadRow item={item} {...rowActions} />
                </li>
              ))}
            </ul>
          ) : null
        }
        hasMore={list.hasNextPage}
        loadingMore={list.isFetchingNextPage}
        onLoadMore={() => void list.fetchNextPage()}
        onRetry={() => void list.refetch()}
        onUpload={onUpload}
        onFiles={(files) => {
          setDropped(files)
          setSheetOpen(true)
        }}
        onClearFilters={() => go({ sort: search.sort })}
        renderCard={(doc) => (
          <DocumentCard
            doc={doc}
            onEdit={dialogs.openEdit}
            onExport={online ? dialogs.openExport : undefined}
            onDownload={online ? (d) => void download(d.id) : undefined}
            onTrash={(d) => void actions.trash(d)}
            onMakeSearchable={online ? dialogs.openOcr : undefined}
          />
        )}
      />
      <UploadSheetContainer
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        initialFiles={dropped}
        onInitialConsumed={() => setDropped(null)}
        onQuota={(details) => {
          setSheetOpen(false)
          dialogs.openQuota(details)
        }}
      />
      <DocumentDialogs controller={dialogs} showLibraryLink={false} />
    </>
  )
}

/** `/app/notes/library`: the student's PDFs with filters, upload, and the dialogs to edit, read with OCR, export and free space. */
export function LibraryContainer({ search }: { search: LibrarySearch }) {
  return (
    <NotesShell>
      <Library search={search} />
    </NotesShell>
  )
}
