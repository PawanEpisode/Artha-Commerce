import type { MarkRecord, MarksInfo } from './annotation-types'
import { serialisedSize } from './geometry'

/** From this share of the plan's marks per document the student gets a quiet notice (PRD 7.3). */
export const NEAR_LIMIT_RATIO = 0.95

export type MarksNotice = 'ok' | 'near' | 'blocked'

export function marksNotice(info: Pick<MarksInfo, 'count' | 'limit'>): MarksNotice {
  if (info.count >= info.limit) return 'blocked'
  return info.count >= info.limit * NEAR_LIMIT_RATIO ? 'near' : 'ok'
}

export interface HeavyPage {
  page: number
  /** Size of the drawings on the page as the server measures them. */
  bytes: number
  drawings: number
}

/** The pages that hold the most ink, heaviest first: where to delete to make room (computed from the cached marks). */
export function heaviestInkPages(
  marks: readonly Pick<MarkRecord, 'kind' | 'page' | 'geometry' | 'deleted_at'>[],
  limit = 5,
): HeavyPage[] {
  const pages = new Map<number, HeavyPage>()
  for (const mark of marks) {
    if (mark.kind !== 'ink' || mark.deleted_at) continue
    const entry = pages.get(mark.page) ?? { page: mark.page, bytes: 0, drawings: 0 }
    entry.bytes += serialisedSize(mark.geometry)
    entry.drawings += 1
    pages.set(mark.page, entry)
  }
  return [...pages.values()].sort((a, b) => b.bytes - a.bytes || a.page - b.page).slice(0, limit)
}

/** "12 KB" for a size in bytes. */
export const inkSizeLabel = (bytes: number) => (bytes < 1024 ? `${bytes} B` : `${Math.round(bytes / 1024)} KB`)
