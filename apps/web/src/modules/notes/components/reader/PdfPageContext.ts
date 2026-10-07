import { createContext, useContext } from 'react'

import type { PageTone } from '../../lib/document-types'
import type { PdfTextContent } from '../../lib/pdf-engine'

/**
 * What a layer inside a page needs to place things: the page's size on screen and in points, and its text. The
 * annotation layer (marks under the text layer, tools and pins above it) reads this with `usePdfPageContext()` and
 * converts between the stored frame and pixels with `lib/coords.ts` (`toViewportRect`, `fromViewportRect`).
 */
export interface PdfPageContextValue {
  /** 1-based page number. */
  page: number
  /** Size of the page box on screen, CSS pixels. */
  width: number
  height: number
  /** CSS pixels per PDF point. */
  scale: number
  /** The page in points (as displayed, intrinsic rotation applied). */
  pageW: number
  pageH: number
  tone: PageTone
  /** The text layer's content once loaded (native or OCR), for anchoring a selection or a search hit. */
  text: PdfTextContent | null
}

export const PdfPageContext = createContext<PdfPageContextValue | null>(null)

export function usePdfPageContext(): PdfPageContextValue {
  const ctx = useContext(PdfPageContext)
  if (!ctx) throw new Error('usePdfPageContext must be used inside a PdfPage')
  return ctx
}
