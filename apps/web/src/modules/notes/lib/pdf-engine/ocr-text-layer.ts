/**
 * The invisible text layer of a scanned page. The worker's OCR returns `words: [[x, y, w, h, "word"], ...]` in the
 * normalised frame; they become the same `LayerItem`s as native text, so the text layer, selection and marks work the
 * same way on a scan. Pure.
 */
import type { OcrWord, PageText } from '../document-types'
import type { LayerItem, PdfTextContent } from './index'

const FOLD = (s: string) => s.normalize('NFKC').toLowerCase()

/**
 * Offsets of each word in the page text. Words come in reading order, so each is searched from where the last one ended;
 * a word the text does not contain (OCR cleaned it up) keeps the running position so later words still line up.
 */
export function wordOffsets(text: string, words: ReadonlyArray<OcrWord>): number[] {
  const folded = FOLD(text)
  const usable = folded.length === text.length
  const hay = usable ? folded : text
  const offsets: number[] = []
  let cursor = 0
  for (const word of words) {
    const needle = usable ? FOLD(word[4]) : word[4]
    const found = needle ? hay.indexOf(needle, cursor) : -1
    if (found === -1) {
      offsets.push(cursor)
    } else {
      offsets.push(found)
      cursor = found + word[4].length
    }
  }
  return offsets
}

/** The text model of an OCR page, or null when the page has no word boxes (a native page, or OCR not done yet). */
export function ocrTextContent(page: Pick<PageText, 'text' | 'words'>): PdfTextContent | null {
  const words = page.words
  if (!words || words.length === 0) return null
  const starts = wordOffsets(page.text, words)
  const items: LayerItem[] = words.map(([x, y, w, h, str], i) => ({
    str,
    x,
    y,
    w,
    h,
    angle: 0,
    start: starts[i] as number,
  }))
  return { text: page.text, items }
}
