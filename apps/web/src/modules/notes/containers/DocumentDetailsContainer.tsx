import {
  Alert,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Skeleton,
  StepDialog,
  Trash2,
} from '@artha/design-system'
import { useEffect, useRef, useState } from 'react'

import { useOnline } from '~/modules/personalization'

import { DeleteDocumentDialog } from '../components/library/DeleteDocumentDialog'
import { useDocumentFormData } from '../hooks/useDocumentFormData'
import { useDocument } from '../hooks/useDocuments'
import { useDocumentActions } from '../hooks/useLibrary'
import { useEnrolledSubjects } from '../hooks/useNotesQueries'
import {
  type DocumentDraft,
  documentPatch,
  draftFromDocument,
  filingFromDocument,
  firstInvalidStep,
  type FormStepId,
  rangeInputsOf,
  sameRanges,
} from '../lib/document-draft'
import type { DocumentDetail } from '../lib/document-types'
import { isRangesOverlap, requestIdOf } from '../lib/errors'
import { notifyDocs } from '../lib/notify-documents'
import { filledRows, overlapRows, type RowProblems, toRangeInputs } from '../lib/page-ranges'
import { DocumentFormStep } from './DocumentFormStep'
import { ReplaceSectionContainer } from './ReplaceSectionContainer'
import { UnlockSectionContainer } from './UnlockSectionContainer'

interface DocumentDetailsContainerProps {
  docId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

type StepKey = FormStepId | 'manage'

const STEPS: StepKey[] = ['details', 'filing', 'ranges', 'manage']
const STEP_LABEL: Record<StepKey, string> = {
  details: 'Details',
  filing: 'Filing',
  ranges: 'Page ranges',
  manage: 'More',
}
const STEP_TITLE: Record<StepKey, string> = {
  details: 'Title, source and tags',
  filing: 'Where it belongs',
  ranges: 'Page ranges',
  manage: 'Newer edition, password and removal',
}

function Loaded({ doc, onOpenChange }: { doc: DocumentDetail; onOpenChange: (open: boolean) => void }) {
  const online = useOnline()
  const actions = useDocumentActions()
  const { subjects } = useEnrolledSubjects()
  const [draft, setDraft] = useState<DocumentDraft>(() => draftFromDocument(doc, subjects))
  const [index, setIndex] = useState(0)
  const [saving, setSaving] = useState(false)
  const [serverProblems, setServerProblems] = useState<RowProblems>({})
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const form = useDocumentFormData(draft.filing)
  const filingTouched = useRef(false)

  // The student's papers may arrive after the dialog opens: until they touch the filing, show it with the right subject.
  useEffect(() => {
    if (filingTouched.current) return
    setDraft((d) => ({ ...d, filing: filingFromDocument(doc, subjects) }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subjects.length])

  const patchDraft = (change: Partial<DocumentDraft>) => {
    if (change.filing) filingTouched.current = true
    setDraft((d) => ({ ...d, ...change }))
  }

  /** Only what changed goes out, with `base_rev` so another device's edit is not silently overwritten. */
  const save = async () => {
    const invalid = firstInvalidStep(draft, doc.page_count)
    if (invalid) return setIndex(STEPS.indexOf(invalid))
    if (filingTouched.current && form.selection === undefined) return setIndex(STEPS.indexOf('filing'))
    const patch = documentPatch(doc, draft, filingTouched.current ? form.selection : undefined)
    const rangesChanged = !sameRanges(draft, doc.ranges)
    if (!patch && !rangesChanged) return onOpenChange(false)
    setSaving(true)
    try {
      if (patch && !(await actions.patch(doc.id, patch))) return
      if (rangesChanged) {
        const { inputs, order } = toRangeInputs(filledRows(draft.rows))
        try {
          const result = await actions.saveRanges(doc.id, inputs)
          notifyDocs.rangesSaved(result.relinked)
        } catch (error) {
          if (isRangesOverlap(error)) {
            setServerProblems(overlapRows(error, order))
            setIndex(STEPS.indexOf('ranges'))
          } else notifyDocs.error(error, 'Could not save the page ranges.')
          return
        }
      }
      notifyDocs.saved()
      onOpenChange(false)
    } finally {
      setSaving(false)
    }
  }

  const step = STEPS[index] ?? 'details'
  const last = index === STEPS.length - 1
  const busy = saving || !online
  const rangeCount = rangeInputsOf(draft).length

  return (
    <>
      <StepDialog
        open
        onOpenChange={onOpenChange}
        title="Edit PDF details"
        description={<span className="break-words">{doc.original_filename}</span>}
        steps={STEPS.map((key) => STEP_LABEL[key])}
        current={index}
        onStepSelect={setIndex}
        stepTitle={STEP_TITLE[step]}
        stepDescription={
          step === 'ranges' && rangeCount > 0
            ? `${rangeCount} ${rangeCount === 1 ? 'range' : 'ranges'} set.`
            : undefined
        }
        onBack={index > 0 ? () => setIndex(index - 1) : undefined}
        aside={
          !online ? (
            <span className="text-sm text-muted-foreground">You are offline. Changes need a connection.</span>
          ) : null
        }
        action={
          <>
            {!last ? (
              <Button variant="outline" onClick={() => setIndex(index + 1)}>
                Next
              </Button>
            ) : null}
            <Button onClick={() => void save()} disabled={busy} loading={saving}>
              Save changes
            </Button>
          </>
        }
      >
        {step === 'manage' ? (
          <div className="space-y-6">
            <UnlockSectionContainer doc={doc} />
            <ReplaceSectionContainer doc={doc} />
            <section aria-labelledby="remove-h" className="space-y-3 rounded-xl border border-border p-4">
              <h4 id="remove-h" className="font-display text-base font-bold">
                Remove this PDF
              </h4>
              <p className="text-sm text-muted-foreground">
                Move to Trash keeps it for a while, with Undo. Delete now removes the PDF and all your marks on it for
                good, and frees the space at once.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  disabled={!online}
                  onClick={() => void actions.trash(doc).then((ok) => ok && onOpenChange(false))}
                >
                  <Trash2 aria-hidden /> Move to Trash
                </Button>
                <Button variant="danger" disabled={!online} onClick={() => setConfirmDelete(true)}>
                  Delete now
                </Button>
              </div>
            </section>
          </div>
        ) : (
          <DocumentFormStep
            step={step}
            draft={draft}
            onDraft={patchDraft}
            form={form}
            pageCount={doc.page_count}
            outline={doc.outline ?? []}
            serverProblems={serverProblems}
            onClearServerProblems={() => setServerProblems({})}
          />
        )}
      </StepDialog>
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

/** Loads the full document (ranges, outline) for the edit dialog, with its own loading and error states. */
export function DocumentDetailsContainer({ docId, open, onOpenChange }: DocumentDetailsContainerProps) {
  const query = useDocument(docId)
  if (!open) return null
  if (query.data) return <Loaded key={query.data.id} doc={query.data} onOpenChange={onOpenChange} />
  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Edit PDF details</DialogTitle>
        <DialogDescription>Loading the PDF…</DialogDescription>
        <div className="mt-4">
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
        </div>
      </DialogContent>
    </Dialog>
  )
}
