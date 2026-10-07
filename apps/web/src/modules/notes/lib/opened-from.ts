import type { ReaderSearch } from './reader-schema'

export type OpenedFrom = 'library' | 'search' | 'aggregate' | 'chapter'

const KEY = 'artha.notes.opened-from'
const FROM: readonly OpenedFrom[] = ['library', 'search', 'aggregate', 'chapter']

/**
 * Where a PDF was opened from, for the `pdf_opened` event. The screen that links to the reader calls
 * `markOpenedFrom('chapter')` just before navigating; the reader reads it once. A link that carries `q` is a search hit,
 * one that carries `ann` comes from a list of marks, and anything else is the library.
 */
export function markOpenedFrom(from: OpenedFrom): void {
  try {
    window.sessionStorage.setItem(KEY, from)
  } catch {
    // Blocked storage only loses the label.
  }
}

export function consumeOpenedFrom(search: Pick<ReaderSearch, 'q' | 'ann'>): OpenedFrom {
  let stored: string | null = null
  try {
    stored = window.sessionStorage.getItem(KEY)
    window.sessionStorage.removeItem(KEY)
  } catch {
    // Same as above.
  }
  if (stored && (FROM as readonly string[]).includes(stored)) return stored as OpenedFrom
  if (search.q) return 'search'
  if (search.ann) return 'aggregate'
  return 'library'
}
