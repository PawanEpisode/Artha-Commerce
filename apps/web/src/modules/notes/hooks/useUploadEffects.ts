import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'

import { notesAnalytics } from '../lib/analytics'
import { notesKeys } from '../lib/keys'
import { notifyDocs } from '../lib/notify-documents'
import { getNotesSettings } from '../lib/settings-api'
import { uploadManager } from '../lib/upload-client'
import type { UploadEvent } from '../lib/upload-manager'
import { useRequestOcr } from './useOcrExport'

/**
 * What happens around an upload that is not drawn by the chip: analytics at the end, the library and usage refresh, the
 * success toast with Open (a different sentence for a scanned or locked PDF), and the "OCR default: always" request. Mounted
 * once in the app layout (with the chip), so it works on every screen. Each document is auto-read at most once.
 */
export function useUploadEffects() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const requestOcr = useRequestOcr()
  const autoRead = useRef(new Set<string>())

  useEffect(() => {
    const refresh = () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: notesKeys.documentLists }),
        qc.invalidateQueries({ queryKey: notesKeys.usage }),
        qc.invalidateQueries({ queryKey: notesKeys.allCounts }),
      ])

    const onCompleted = async (event: Extract<UploadEvent, { type: 'completed' }>) => {
      const { item, document, durationMs } = event
      const scanned = document.is_scanned === true
      const encrypted = document.is_encrypted || document.status === 'needs_password'
      notesAnalytics.pdfUploadCompleted({
        bytes: item.bytes,
        pages: document.page_count,
        durationMs,
        encrypted,
        scanned,
      })
      void refresh()
      // A duplicate waits for the student's choice in the chip, so no "added" toast yet.
      if (document.duplicate_of) return
      const open = () => void navigate({ to: '/app/notes/pdf/$docId', params: { docId: document.id } })
      const settings =
        scanned && !encrypted
          ? await qc
              .fetchQuery({ queryKey: notesKeys.settings, queryFn: getNotesSettings, staleTime: 60_000 })
              .catch(() => undefined)
          : undefined
      if (encrypted) notifyDocs.addedLocked(open)
      else if (scanned && settings?.ocr_default !== 'never') notifyDocs.addedScanned(open)
      else notifyDocs.added(open)
      if (
        scanned &&
        !encrypted &&
        settings?.ocr_default === 'always' &&
        document.can_copy !== false &&
        !autoRead.current.has(document.id)
      ) {
        autoRead.current.add(document.id)
        const outcome = await requestOcr(document, { lang: settings.ocr_lang })
        if (!outcome.ok && outcome.reason === 'quota') notifyDocs.ocrQuota()
      }
    }

    return uploadManager.onEvent((event) => {
      if (event.type === 'completed') void onCompleted(event)
      else if (event.type === 'failed') {
        notesAnalytics.pdfUploadFailed({
          bytes: event.item.bytes,
          pages: event.item.pages,
          reason: event.failure.reason,
        })
        void refresh()
      }
    })
  }, [qc, navigate, requestOcr])
}
