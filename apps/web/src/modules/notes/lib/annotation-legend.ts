import type { SwatchOption } from '@artha/design-system'

import { type ColorKey, INK_COLORS, MARKUP_COLORS, type MarkupColor, type NotesSettings } from './annotation-types'

/** What the server gives a student who has not renamed the colours (ERD 2.11). Used until `GET settings/` answers. */
export const DEFAULT_LEGEND: Record<MarkupColor, string> = {
  y: 'Important',
  g: 'Formula',
  b: 'Section or rule',
  p: 'Doubt',
  o: 'Example',
}

/** Pens have no legend: a plain name that does not depend on seeing the colour. */
export const INK_NAMES: Record<(typeof INK_COLORS)[number], string> = {
  i1: 'Graphite pen',
  i2: 'Red pen',
  i3: 'Blue pen',
  i4: 'Green pen',
  i5: 'Purple pen',
}

/** The colour as a word, spoken after the page in the list ("Highlight, page 14, yellow (Formula)"). */
export const COLOR_WORDS: Record<ColorKey, string> = {
  y: 'yellow',
  g: 'green',
  b: 'blue',
  p: 'pink',
  o: 'orange',
  i1: 'grey',
  i2: 'red',
  i3: 'blue',
  i4: 'green',
  i5: 'purple',
}

export type Legend = Partial<Record<MarkupColor, string>>

export const isMarkupColor = (key: string | null | undefined): key is MarkupColor =>
  !!key && (MARKUP_COLORS as readonly string[]).includes(key)
export const isInkColor = (key: string | null | undefined): key is (typeof INK_COLORS)[number] =>
  !!key && (INK_COLORS as readonly string[]).includes(key)

/** The student's name for a colour: the legend for highlights, the pen name for ink. Never empty for a known key. */
export function colorName(key: ColorKey | null | undefined, legend: Legend = DEFAULT_LEGEND): string {
  if (!key) return ''
  if (isInkColor(key)) return INK_NAMES[key]
  return legend[key]?.trim() || DEFAULT_LEGEND[key]
}

export const legendOptions = (legend: Legend = DEFAULT_LEGEND): SwatchOption[] =>
  MARKUP_COLORS.map((key) => ({ key, name: colorName(key, legend) }))

export const inkOptions = (): SwatchOption[] => INK_COLORS.map((key) => ({ key, name: INK_NAMES[key] }))

export const legendOf = (settings: Pick<NotesSettings, 'color_legend'> | undefined): Legend =>
  settings?.color_legend ?? DEFAULT_LEGEND
