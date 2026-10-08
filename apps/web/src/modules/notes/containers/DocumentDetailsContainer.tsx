import {
  Alert,
  Button,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
} from '@artha/design-system'
import { useState } from 'react'

import { useOnline } from '~/modules/personalization'

import { DeleteDocumentDialog } from '../components/library/DeleteDocumentDialog'
import { type DetailsDraft, DocumentDetailsSheet } from '../components/library/DocumentDetailsSheet'
import { useDocument } from '../hooks/useDocuments'
import { useDocumentActions } from '../hooks/useLibrary'
import { useNoteActions } from '../hooks/useNoteActions'
import { useTags } from '../hooks/useNotesQueries'
import { linkFields } from '../lib/chapter-link'
import type { DocumentDetail, DocumentPatch } from '../lib/document-types'
import { requestIdOf } from '../lib/errors'
import { notifyDocs } from '../lib/notify-documents'
import { ChapterPicker } from './ChapterPicker'
import { RangeEditorContainer } from './RangeEditorContainer'
import { ReplaceSectionContainer } from './ReplaceSectionContainer'
import { UnlockSectionContainer } from './UnlockSectionContainer'

interface DocumentDetailsContainerProps {
  docId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

function Loaded({ doc, onOpenChange }: { doc: DocumentDetail; onOpenChange: (open: boolean) => void }) {
  const online = useOnline()
  const tags = useTags()
  const noteActions = useNoteActions()
  const actions = useDocumentActions()
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  /** Only what changed goes out, with `base_rev` so another device's edit is not silently overwritten. */
  const save = async (draft: DetailsDraft) => {
    const patch: DocumentPatch = { base_rev: doc.rev }
    if (draft.title.trim() !== doc.title) patch.title = draft.title.trim()
    if (draft.source_kind !== doc.source_kind) patch.source_kind = draft.source_kind
    if ((draft.edition_label.trim() || null) !== doc.edition_label)
      patch.edition_label = draft.edition_label.trim() || null
    const before = doc.tags
      .map((t) => t.id)
      .sort()
      .join(',')
    if (before !== [...draft.tag_ids].sort().join(',')) patch.tag_ids = draft.tag_ids
    if (Object.keys(patch).length === 1) return onOpenChange(false)
    setSaving(true)
    const saved = await actions.patch(doc.id, patch)
    setSaving(false)
    if (saved) {
      notifyDocs.saved()
      onOpenChange(false)
    }
  }

  return (
    <>
      <DocumentDetailsSheet
        key={doc.id}
        open
        onOpenChange={onOpenChange}
        doc={doc}
        tags={tags.data ?? []}
        onCreateTag={noteActions.addTag}
        online={online}
        saving={saving}
        onSave={(draft) => void save(draft)}
        onTrash={() => void actions.trash(doc).then((ok) => ok && onOpenChange(false))}
        onDeleteNow={() => setConfirmDelete(true)}
        chapterSlot={
          <ChapterPicker
            link={doc.link}
            disabled={!online}
            onSelect={(selection) => void actions.patch(doc.id, { base_rev: doc.rev, ...linkFields(selection) })}
          />
        }
        rangesSlot={<RangeEditorContainer doc={doc} />}
        replaceSlot={
          <>
            <UnlockSectionContainer doc={doc} />
            <ReplaceSectionContainer doc={doc} />
          </>
        }
      />
      <DeleteDocumentDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        doc={doc}
        busy={deleting}
        onConfirm={() => {
          setDeleting(true)
          void actions.purge(doc).then((ok) => {
            setDeleting(false)
            if (ok) {
              setConfirmDelete(false)
              onOpenChange(false)
            }
          })
        }}
      />
    </>
  )
}

/** Loads the full document (ranges, outline) for the details sheet, with its own loading and error states. */
export function DocumentDetailsContainer({ docId, open, onOpenChange }: DocumentDetailsContainerProps) {
  const query = useDocument(docId)
  if (!open) return null
  if (query.data) return <Loaded doc={query.data} onOpenChange={onOpenChange} />
  return (
    <Sheet open onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="sm:mx-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>Edit details</SheetTitle>
          <SheetDescription>Loading the PDF…</SheetDescription>
        </SheetHeader>
        {query.isError ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              <span>We could not load this PDF.</span>
              {requestIdOf(query.error) ? <span className="text-xs">Request {requestIdOf(query.error)}</span> : null}
              <Button size="sm" variant="outline" onClick={() => void query.refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          <div aria-busy="true" className="space-y-3">
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
