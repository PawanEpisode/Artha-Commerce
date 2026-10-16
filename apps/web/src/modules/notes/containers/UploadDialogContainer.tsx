import { Button, StepDialog } from '@artha/design-system'
import { useEffect, useRef, useState } from 'react'

import { useOnline } from '~/modules/personalization'

import { FileStep, type FileStepState, uploadLimitsText } from '../components/library/steps/FileStep'
import { useDocumentFormData } from '../hooks/useDocumentFormData'
import { useUsage } from '../hooks/useNotesQueries'
import { useUploads } from '../hooks/useUploads'
import { notesAnalytics } from '../lib/analytics'
import {
  type DocumentDraft,
  draftFromFile,
  filingProblem,
  firstInvalidStep,
  type FormStepId,
  rangeInputsOf,
  titleProblem,
  uploadDetails,
} from '../lib/document-draft'
import type { DocumentQuotaDetails } from '../lib/errors'
import { formatBytes, pluralize } from '../lib/format'
import { filledRows, validateRows } from '../lib/page-ranges'
import { quickCheck } from '../lib/pdf-quick-check'
import {
  checkBeforeUpload,
  type FileFacts,
  limitsFromUsage,
  MIB,
  quotaFromRefusal,
  type UploadRefusal,
} from '../lib/upload-check'
import { DocumentFormStep } from './DocumentFormStep'

interface UploadDialogContainerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Files dropped on the empty state before the dialog existed: checked as soon as it opens. */
  initialFiles?: File[] | null
  onInitialConsumed?: () => void
  /** A quota refusal: the library opens the quota sheet with the details. */
  onQuota: (details: DocumentQuotaDetails) => void
  /** "Replace edition": the file is a newer edition of this document. It has one step: no details to fill in. */
  replace?: { docId: string; title: string }
}

type StepKey = 'file' | FormStepId

const STEP_LABEL: Record<StepKey, string> = {
  file: 'PDF',
  details: 'Details',
  filing: 'Filing',
  ranges: 'Page ranges',
}
const STEP_TITLE: Record<StepKey, string> = {
  file: 'Choose your PDF',
  details: 'Tell us about it',
  filing: 'Where does it belong?',
  ranges: 'Which pages are which chapter?',
}
const STEP_HINT: Partial<Record<StepKey, string>> = {
  details: 'Everything except the title is optional, and you can change any of it later.',
  filing: 'Skip this and the PDF stays Unfiled until you file it.',
}

/**
 * The upload dialog's brain: reads the chosen file's name, size and page count (the pdf.js adapter, never the network),
 * refuses a file over a limit BEFORE any byte moves, then walks through Details, Filing and Page ranges (all optional, and
 * "Upload now" skips ahead). On Upload it hands the file and what was filled in to the module-level upload manager, which keeps
 * going after the dialog closes (the chip in the app layout shows it).
 */
export function UploadDialogContainer({
  open,
  onOpenChange,
  initialFiles,
  onInitialConsumed,
  onQuota,
  replace,
}: UploadDialogContainerProps) {
  const online = useOnline()
  const usage = useUsage()
  const { start } = useUploads()
  const [state, setState] = useState<FileStepState>({ step: 'choose' })
  const file = useRef<File | null>(null)
  const [editionLabel, setEditionLabel] = useState('')
  const [index, setIndex] = useState(0)
  const [draft, setDraft] = useState<DocumentDraft>(() => draftFromFile(''))
  const form = useDocumentFormData(draft.filing)
  const limits = limitsFromUsage(usage.data)
  const used = usage.data
    ? { storageBytes: usage.data.used.storage_bytes, documents: usage.data.used.documents ?? 0 }
    : undefined

  const steps: StepKey[] = replace ? ['file'] : ['file', 'details', 'filing', 'ranges']
  const step = steps[index] ?? 'file'
  const ready = state.step === 'ready'
  const pages = ready ? state.file.pages : null

  const choose = async (picked: File) => {
    file.current = picked
    setIndex(0)
    setState({ step: 'checking', name: picked.name, bytes: picked.size })
    // Cheap refusals first: nothing to read when the file is already too big or not a PDF.
    const early: FileFacts = { name: picked.name, type: picked.type, bytes: picked.size, pages: null }
    let refusal: UploadRefusal | null = checkBeforeUpload(early, limits, used)
    let pageCount: number | null = null
    let encrypted = false
    if (!refusal) {
      const result = await quickCheck(picked)
      pageCount = result.pages
      encrypted = result.encrypted
      refusal = result.notPdf ? { reason: 'type' } : checkBeforeUpload({ ...early, pages: pageCount }, limits, used)
    }
    const facts: FileFacts = { ...early, pages: pageCount }
    if (refusal) {
      reportRefusal(refusal, facts)
      setState({ step: 'refused', file: facts, refusal })
    } else {
      setDraft(draftFromFile(picked.name))
      setState({ step: 'ready', file: facts, encrypted })
    }
  }

  const reportRefusal = (refusal: UploadRefusal, facts: FileFacts) => {
    if (refusal.reason === 'quota') notesAnalytics.quotaBlocked(refusal.kind)
    else
      notesAnalytics.pdfUploadFailed({
        bytes: facts.bytes,
        pages: facts.pages,
        reason: refusal.reason,
      })
  }

  const initial = useRef(false)
  useEffect(() => {
    if (!open || !initialFiles?.[0] || initial.current) return
    initial.current = true
    void choose(initialFiles[0]).finally(() => {
      initial.current = false
      onInitialConsumed?.()
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialFiles])

  // After space is freed (the quota sheet deleted a PDF) the same file may fit now: check again without a new pick.
  useEffect(() => {
    if (state.step !== 'refused' || state.refusal.reason !== 'quota') return
    const next = checkBeforeUpload(state.file, limits, used)
    if (!next) setState({ step: 'ready', file: state.file, encrypted: false })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usage.data])

  const reset = () => {
    file.current = null
    setEditionLabel('')
    setIndex(0)
    setDraft(draftFromFile(''))
    setState({ step: 'choose' })
  }

  const patchDraft = (change: Partial<DocumentDraft>) => setDraft((d) => ({ ...d, ...change }))

  const stepProblem = (key: StepKey): boolean => {
    if (key === 'details') return titleProblem(draft.title) !== null
    if (key === 'filing') return filingProblem(draft.filing) !== null || form.selection === undefined
    if (key === 'ranges') return Object.keys(validateRows(filledRows(draft.rows), pages)).length > 0
    return !ready
  }

  const startUpload = () => {
    if (state.step !== 'ready' || !file.current) return
    const invalid = firstInvalidStep(draft, pages)
    if (!replace && invalid) return setIndex(steps.indexOf(invalid))
    if (!replace && form.selection === undefined) return setIndex(steps.indexOf('filing'))
    notesAnalytics.pdfUploadStarted({ bytes: state.file.bytes, pages: state.file.pages })
    const selection = replace ? null : form.selection
    start(file.current, {
      pages: state.file.pages,
      ...(replace
        ? { replaces: { documentId: replace.docId, editionLabel } }
        : {
            sourceKind: draft.source_kind,
            chapterId: selection?.chapterId ?? null,
            topicId: selection?.topicId ?? null,
            subjectId: selection && !selection.chapterId ? selection.subjectId : null,
            details: uploadDetails(draft, file.current.name),
            ranges: rangeInputsOf(draft),
          }),
    })
    onOpenChange(false)
    reset()
  }

  const manage = () => {
    if (state.step !== 'refused' || state.refusal.reason !== 'quota') return
    onQuota(quotaFromRefusal(state.refusal, usage.data?.plan ?? 'free', usage.data?.largest_documents))
  }

  const last = index === steps.length - 1
  const usedText = usage.data
    ? `${formatBytes(usage.data.used.storage_bytes)} of ${Math.round((usage.data.limits.max_storage_mb * MIB) / MIB)} MB used.`
    : `Your plan holds ${pluralize(limits.maxDocuments, 'PDF')} and ${limits.maxStorageMb} MB.`

  const action = !ready ? undefined : last ? (
    <Button onClick={startUpload} disabled={!online}>
      {replace ? 'Replace' : 'Upload'}
    </Button>
  ) : (
    <>
      <Button variant="outline" onClick={startUpload} disabled={!online}>
        Upload now
      </Button>
      <Button onClick={() => setIndex(index + 1)} disabled={stepProblem(step)}>
        Next
      </Button>
    </>
  )

  return (
    <StepDialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next)
        if (!next) reset()
      }}
      title={replace ? 'Replace with a newer edition' : 'Upload a PDF'}
      description={
        <>
          {replace
            ? `Choose the newer file for “${replace.title}”. Your marks move to it where the words match. `
            : null}
          Your PDF is private to you. {usedText}
        </>
      }
      steps={steps.map((key) => STEP_LABEL[key])}
      current={index}
      stepTitle={step === 'file' && ready ? 'Your PDF' : STEP_TITLE[step]}
      stepDescription={step === 'file' ? uploadLimitsText(limits) : STEP_HINT[step]}
      onBack={index > 0 ? () => setIndex(index - 1) : undefined}
      action={action}
    >
      {step === 'file' ? (
        <FileStep
          state={state}
          limits={limits}
          online={online}
          onFiles={(files) => files[0] && void choose(files[0])}
          onChooseAnother={reset}
          onManageStorage={manage}
          replacing={replace ? { label: editionLabel, onLabelChange: setEditionLabel } : undefined}
        />
      ) : (
        <DocumentFormStep step={step} draft={draft} onDraft={patchDraft} form={form} pageCount={pages} />
      )}
    </StepDialog>
  )
}
