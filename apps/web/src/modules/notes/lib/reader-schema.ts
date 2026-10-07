import { z } from 'zod'

/** Panels the reader can have open. `annotations` is the list of marks (built by the annotation layer). */
export const READER_PANELS = ['outline', 'search', 'annotations'] as const
export type ReaderPanel = (typeof READER_PANELS)[number]

/** Tools of the annotation layer. The reader only keeps the name in the URL; the layer owns what they do. */
export const READER_TOOLS = ['highlight', 'underline', 'pen', 'text', 'sticky', 'bookmark', 'area', 'eraser'] as const
export type ReaderTool = (typeof READER_TOOLS)[number]

export const MIN_ZOOM_PERCENT = 25
export const MAX_ZOOM_PERCENT = 500

/** `fit` (fit width) or a percent: CSS pixels per PDF point times 100. */
export type ZoomSpec = 'fit' | number

/**
 * `/app/notes/pdf/$docId?page=&zoom=&q=&panel=&tool=&ann=`. Everything is optional and a bad value is dropped, never an
 * error, so a hand-edited or stale link still opens the document. The URL wins over the stored resume position.
 * TanStack parses `zoom=125` to a number and `zoom=fit` stays text, so both are accepted.
 */
export const readerSearchSchema = z.object({
  page: z.coerce.number().int().min(1).max(100_000).optional().catch(undefined),
  zoom: z
    .union([z.literal('fit'), z.coerce.number().min(MIN_ZOOM_PERCENT).max(MAX_ZOOM_PERCENT)])
    .transform((v): ZoomSpec => (v === 'fit' ? 'fit' : Math.round(v)))
    .optional()
    .catch(undefined),
  q: z.string().trim().min(1).max(200).optional().catch(undefined),
  panel: z.enum(READER_PANELS).optional().catch(undefined),
  tool: z.enum(READER_TOOLS).optional().catch(undefined),
  ann: z.uuid().optional().catch(undefined),
})
export type ReaderSearch = z.infer<typeof readerSearchSchema>
