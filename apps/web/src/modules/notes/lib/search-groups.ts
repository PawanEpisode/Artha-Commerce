import { pluralize } from './format'
import type { MarkSearchHit, NotSearchableReason, PdfSearchHit, SearchMeta } from './library-types'

export const PAGES_PER_DOCUMENT = 5

export interface PdfGroup {
  documentId: string
  title: string
  hits: PdfSearchHit[]
  /** Pages found beyond the five shown. */
  more: number
}

/** Groups PDF page hits by document (best document first), the top five pages each, pages in page order. */
export function groupPdfHits(hits: readonly PdfSearchHit[], perDocument = PAGES_PER_DOCUMENT): PdfGroup[] {
  const groups = new Map<string, { title: string; hits: PdfSearchHit[] }>()
  for (const hit of hits) {
    const group = groups.get(hit.document_id) ?? { title: hit.document_title, hits: [] }
    group.hits.push(hit)
    groups.set(hit.document_id, group)
  }
  return [...groups.entries()].map(([documentId, group]) => {
    const top = [...group.hits].sort((a, b) => a.rank - b.rank || a.page - b.page).slice(0, perDocument)
    return {
      documentId,
      title: group.title,
      hits: top.sort((a, b) => a.page - b.page),
      more: Math.max(0, group.hits.length - top.length),
    }
  })
}

export const isPdfHit = (hit: { type: string }): hit is PdfSearchHit => hit.type === 'pdf'
export const isMarkHit = (hit: { type: string }): hit is MarkSearchHit => hit.type === 'highlight'

/** "2 documents are still being indexed", or null. */
export const indexingText = (meta: SearchMeta | undefined) =>
  meta && meta.indexing_documents > 0
    ? `${pluralize(meta.indexing_documents, 'document')} ${meta.indexing_documents === 1 ? 'is' : 'are'} still being indexed.`
    : null

export interface NotSearchable {
  total: number
  /** Documents the student can make searchable (scanned) and the ones that need a password. */
  scanned: number
  locked: number
  pending: number
  text: string
}

/** "3 documents cannot be searched yet (locked or scanned)." Pending ones are covered by the indexing line instead. */
export function notSearchable(meta: SearchMeta | undefined): NotSearchable | null {
  if (!meta) return null
  const count = (reason: NotSearchableReason) => meta.not_searchable.filter((d) => d.reason === reason).length
  const scanned = count('scanned')
  const locked = count('locked')
  const total = scanned + locked
  if (total === 0) return null
  const why = scanned > 0 && locked > 0 ? 'locked or scanned' : locked > 0 ? 'locked' : 'scanned'
  return {
    total,
    scanned,
    locked,
    pending: count('pending'),
    text: `${pluralize(total, 'document')} cannot be searched yet (${why}).`,
  }
}
