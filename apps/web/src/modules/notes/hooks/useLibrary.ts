import { keepPreviousData, useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useMemo } from 'react'

import { notesAnalytics, type QuotaKind } from '../lib/analytics'
import { isWorking } from '../lib/document-badges'
import {
  type DocumentDetail,
  type DocumentListParams,
  type DocumentPatch,
  type DocumentSummary,
  type RangeInput,
} from '../lib/document-types'
import {
  abortDocument,
  deleteDocument,
  listDocuments,
  patchDocument,
  putRanges,
  restoreDocument,
} from '../lib/documents-api'
import { documentQuotaExceeded, errorCode, isFeatureDisabled, isNotFound } from '../lib/errors'
import { formatBytes } from '../lib/format'
import { notesKeys } from '../lib/keys'
import { notifyDocs } from '../lib/notify-documents'

export const LIST_POLL_MS = 3000

/** A 404 or a switched-off flag will not change by asking again. */
const retryUnlessFinal = (failures: number, error: unknown) =>
  failures < 2 && !isNotFound(error) && !isFeatureDisabled(error)

/**
 * The library list, a page at a time by cursor (a library holds up to 100 PDFs). While any card is being prepared or
 * read by OCR the list asks again every few seconds, so a card flips to Ready or shows OCR progress without a refresh.
 */
export function useDocumentList(params: DocumentListParams, enabled = true) {
  return useInfiniteQuery({
    queryKey: notesKeys.documents({ ...params, cursor: undefined }),
    queryFn: ({ pageParam }) => listDocuments({ ...params, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    enabled,
    retry: retryUnlessFinal,
    refetchInterval: (query) => (query.state.data?.pages.some((p) => p.items.some(isWorking)) ? LIST_POLL_MS : false),
  })
}

export const flattenDocuments = (pages: ReadonlyArray<{ items: DocumentSummary[] }> | undefined): DocumentSummary[] =>
  pages?.flatMap((p) => p.items) ?? []

/** "Continue reading": up to three ready documents the student opened last (the API orders by `last_opened_at`). */
export function useContinueReading(enabled = true) {
  const query = useQuery({
    queryKey: notesKeys.documents({ continue: true }),
    queryFn: () => listDocuments({ status: 'ready', sort: 'recent', limit: 3 }),
    enabled,
    retry: retryUnlessFinal,
    staleTime: 30_000,
  })
  const items = useMemo(() => (query.data?.items ?? []).filter((d) => d.last_opened_at !== null), [query.data])
  return { items, isPending: query.isPending, isError: query.isError, error: query.error, refetch: query.refetch }
}

/** Titles of the student's documents by id, for rows (marks) that only know the document id. One cheap list, cached. */
export function useDocumentTitles(enabled = true) {
  const query = useQuery({
    queryKey: notesKeys.documents({ titles: true }),
    queryFn: () => listDocuments({ limit: 100 }),
    enabled,
    staleTime: 60_000,
    retry: retryUnlessFinal,
  })
  return useMemo(() => new Map((query.data?.items ?? []).map((d) => [d.id, d.title])), [query.data])
}

const kindOf = (kind: string): QuotaKind =>
  kind === 'storage' || kind === 'documents' || kind === 'ocr' || kind === 'export' ? kind : 'storage'

/**
 * Every write a library card can make. Each shows its outcome, refreshes the lists, counts and usage it touches, and
 * hands a quota error back (the caller opens the quota sheet) instead of toasting it.
 */
export function useDocumentActions() {
  const qc = useQueryClient()

  const refresh = useCallback(
    () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: notesKeys.documentLists }),
        qc.invalidateQueries({ queryKey: notesKeys.allCounts }),
        qc.invalidateQueries({ queryKey: notesKeys.aggregates }),
        qc.invalidateQueries({ queryKey: notesKeys.overviews }),
        qc.invalidateQueries({ queryKey: notesKeys.usage }),
      ]),
    [qc],
  )

  const restore = useCallback(
    async (doc: Pick<DocumentSummary, 'id'>) => {
      try {
        const restored = await restoreDocument(doc.id)
        qc.setQueryData(notesKeys.document(doc.id), restored)
        notifyDocs.restored()
        await refresh()
        return { ok: true as const }
      } catch (error) {
        const quota = documentQuotaExceeded(error)
        if (quota) {
          notesAnalytics.quotaBlocked(kindOf(quota.kind))
          return { ok: false as const, quota }
        }
        notifyDocs.error(error, 'Could not restore the PDF.')
        return { ok: false as const }
      }
    },
    [qc, refresh],
  )

  /** Trash with a 10 second Undo. A document whose upload never finished is released instead (nothing to keep). */
  const trash = useCallback(
    async (doc: Pick<DocumentSummary, 'id' | 'status'>) => {
      try {
        if (doc.status === 'reserved') await abortDocument(doc.id)
        else await deleteDocument(doc.id)
        if (doc.status !== 'reserved') notifyDocs.trashed(() => void restore(doc))
        await refresh()
        return true
      } catch (error) {
        if (errorCode(error) === 'not_trashable') {
          await abortDocument(doc.id).catch(() => undefined)
          await refresh()
          return true
        }
        notifyDocs.error(error, 'Could not move the PDF to Trash.')
        return false
      }
    },
    [refresh, restore],
  )

  /** Permanent: frees the space at once. The caller has already confirmed. */
  const purge = useCallback(
    async (doc: Pick<DocumentSummary, 'id' | 'bytes'>) => {
      try {
        await deleteDocument(doc.id, true)
        qc.removeQueries({ queryKey: notesKeys.document(doc.id) })
        notifyDocs.purged(formatBytes(doc.bytes))
        await refresh()
        return true
      } catch (error) {
        notifyDocs.error(error, 'Could not delete the PDF.')
        return false
      }
    },
    [qc, refresh],
  )

  const patch = useCallback(
    async (id: string, body: DocumentPatch): Promise<DocumentDetail | undefined> => {
      try {
        const saved = await patchDocument(id, body)
        qc.setQueryData(notesKeys.document(id), saved)
        await refresh()
        return saved
      } catch (error) {
        notifyDocs.error(error, 'Could not save the details.')
        return undefined
      }
    },
    [qc, refresh],
  )

  /** Replaces the page ranges. The caller maps a 409 `ranges_overlap` to the rows, so errors are thrown back. */
  const saveRanges = useCallback(
    async (id: string, ranges: RangeInput[]) => {
      const result = await putRanges(id, ranges)
      await qc.invalidateQueries({ queryKey: notesKeys.document(id), exact: true })
      await refresh()
      return result
    },
    [qc, refresh],
  )

  return { restore, trash, purge, patch, saveRanges, refresh }
}
