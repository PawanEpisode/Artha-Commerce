import { COLOR_WORDS, colorName, type Legend } from './annotation-legend'
import type { Annotation, ColorKey, MarkKind } from './annotation-types'

/** The words for each kind, in the list and in what a screen reader says. */
export const KIND_LABEL: Record<MarkKind, string> = {
  highlight: 'Highlight',
  underline: 'Underline',
  ink: 'Drawing',
  textbox: 'Text box',
  sticky: 'Note',
  bookmark: 'Bookmark',
  area: 'Area',
}

type Labelled = Pick<Annotation, 'kind' | 'page' | 'color' | 'comment' | 'quote_exact'>

const clean = (text: string) => text.replace(/\s+/g, ' ').trim()
const cut = (text: string, max: number) => (text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text)

/** What the mark says: the quoted text for markup, the student's own words for notes, text boxes and bookmarks. */
export function markPreview(mark: Pick<Annotation, 'kind' | 'comment' | 'quote_exact'>, max = 140): string {
  const quote = clean(mark.quote_exact ?? '')
  const comment = clean(mark.comment)
  const text = mark.kind === 'highlight' || mark.kind === 'underline' ? quote || comment : comment || quote
  return cut(text, max)
}

/** "yellow (Formula)" for a highlight; "red pen" for ink. Colour is a word here, never only a swatch. */
export function colorPhrase(key: ColorKey | null, legend: Legend): string {
  if (!key) return ''
  const name = colorName(key, legend)
  return key.startsWith('i') ? name : `${COLOR_WORDS[key]} (${name})`
}

/**
 * The row of the annotation list, and the label of a mark on the page: "Highlight, page 14, yellow (Formula), ITC blocked
 * credits". The list is the screen-reader alternative to marks on the canvas (PRD 11), so it carries everything.
 */
export function describeMark(mark: Labelled, legend: Legend, previewMax = 140): string {
  return [KIND_LABEL[mark.kind], `page ${mark.page}`, colorPhrase(mark.color, legend), markPreview(mark, previewMax)]
    .filter(Boolean)
    .join(', ')
}

/** The first words of a row, shown and spoken the same way: "Highlight, page 14". */
export const markHeading = (mark: Pick<Annotation, 'kind' | 'page'>) => `${KIND_LABEL[mark.kind]}, page ${mark.page}`
