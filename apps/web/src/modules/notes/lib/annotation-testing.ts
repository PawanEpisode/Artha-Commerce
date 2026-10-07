import type { Annotation, BatchOpBody, MarkRecord } from './annotation-types'
import { UNFILED_LINK } from './testing'

/** Test factories for marks. Not imported by app code. */
export const DOC = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'

export function makeAnnotation(overrides: Partial<Annotation> = {}): Annotation {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    document_id: DOC,
    page: 14,
    kind: 'highlight',
    geometry: { quads: [[0.1, 0.2, 0.5, 0.02]] },
    color: 'y',
    comment: '',
    quote_exact: 'ITC blocked credits',
    quote_prefix: null,
    quote_suffix: null,
    text_start: null,
    text_end: null,
    anchor_engine: 'pdfjs',
    link: UNFILED_LINK,
    chapter_source: 'none',
    tags: [],
    recall_card_id: null,
    rev: 1,
    seq: 1,
    device_id: 'device-a',
    created_at: '2026-10-01T10:00:00Z',
    updated_at: '2026-10-01T10:00:00Z',
    deleted_at: null,
    ...overrides,
  }
}

export const makeMark = (overrides: Partial<MarkRecord> = {}): MarkRecord => ({ ...makeAnnotation(), ...overrides })

let stamp = 1000
/** A queue entry as the shared queue stores it, with a strictly increasing time. */
export function entry(body: BatchOpBody, clientId = `c${stamp}`) {
  stamp += 1
  return { clientId, body: body as Record<string, unknown>, queuedAt: stamp }
}
