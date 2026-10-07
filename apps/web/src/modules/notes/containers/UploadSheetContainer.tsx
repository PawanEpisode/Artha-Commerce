import { useEffect, useRef, useState } from 'react'

import { useOnline } from '~/modules/personalization'

import { UploadSheet, type UploadSheetState } from '../components/library/UploadSheet'
import { useUsage } from '../hooks/useNotesQueries'
import { useUploads } from '../hooks/useUploads'
import { notesAnalytics } from '../lib/analytics'
import type { DocumentQuotaDetails } from '../lib/errors'
import { formatBytes } from '../lib/format'
import { quickCheck } from '../lib/pdf-quick-check'
import {
  checkBeforeUpload,
  type FileFacts,
  limitsFromUsage,
  MIB,
  quotaFromRefusal,
  type UploadRefusal,
} from '../lib/upload-check'

interface UploadSheetContainerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Files dropped on the empty state before the sheet existed: checked as soon as the sheet opens. */
  initialFiles?: File[] | null
  onInitialConsumed?: () => void
  /** A quota refusal: the library opens the quota sheet with the details. */
  onQuota: (details: DocumentQuotaDetails) => void
}

/**
 * The upload sheet's brain: reads the chosen file's name, size and page count (the pdf.js adapter, never the network),
 * refuses a file over a limit BEFORE any byte moves, and on Upload hands the file to the module-level upload manager,
 * which keeps going after the sheet closes (the chip in the app layout shows it).
 */
export function UploadSheetContainer({
  open,
  onOpenChange,
  initialFiles,
  onInitialConsumed,
  onQuota,
}: UploadSheetContainerProps) {
  const online = useOnline()
  const usage = useUsage()
  const { start } = useUploads()
  const [state, setState] = useState<UploadSheetState>({ step: 'choose' })
  const file = useRef<File | null>(null)
  const limits = limitsFromUsage(usage.data)
  const used = usage.data
    ? { storageBytes: usage.data.used.storage_bytes, documents: usage.data.used.documents ?? 0 }
    : undefined

  const choose = async (picked: File) => {
    file.current = picked
    setState({ step: 'checking', name: picked.name, bytes: picked.size })
    // Cheap refusals first: nothing to read when the file is already too big or not a PDF.
    const early: FileFacts = { name: picked.name, type: picked.type, bytes: picked.size, pages: null }
    let refusal: UploadRefusal | null = checkBeforeUpload(early, limits, used)
    let pages: number | null = null
    let encrypted = false
    if (!refusal) {
      const result = await quickCheck(picked)
      pages = result.pages
      encrypted = result.encrypted
      refusal = result.notPdf ? { reason: 'type' } : checkBeforeUpload({ ...early, pages }, limits, used)
    }
    const facts: FileFacts = { ...early, pages }
    if (refusal) {
      reportRefusal(refusal, facts)
      setState({ step: 'refused', file: facts, refusal })
    } else {
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
    setState({ step: 'choose' })
  }

  const startUpload = () => {
    if (state.step !== 'ready' || !file.current) return
    notesAnalytics.pdfUploadStarted({ bytes: state.file.bytes, pages: state.file.pages })
    start(file.current, { pages: state.file.pages })
    onOpenChange(false)
    reset()
  }

  const manage = () => {
    if (state.step !== 'refused' || state.refusal.reason !== 'quota') return
    onQuota(quotaFromRefusal(state.refusal, usage.data?.plan ?? 'free', usage.data?.largest_documents))
  }

  return (
    <UploadSheet
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next)
        if (!next) reset()
      }}
      state={state}
      limits={limits}
      online={online}
      usedText={
        usage.data
          ? `${formatBytes(usage.data.used.storage_bytes)} of ${Math.round((usage.data.limits.max_storage_mb * MIB) / MIB)} MB used.`
          : undefined
      }
      onFiles={(files) => files[0] && void choose(files[0])}
      onUpload={startUpload}
      onChooseAnother={reset}
      onManageStorage={manage}
    />
  )
}
