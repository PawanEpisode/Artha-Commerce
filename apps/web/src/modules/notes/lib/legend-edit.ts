import { COLOR_KEYS, type ColorKey, type ColorLegend } from './library-types'

export const LEGEND_NAME_MAX = 24

export type LegendErrors = Partial<Record<ColorKey, string>>

/** Names are trimmed and compared without regard to case or inner spacing, so "Formula" and "formula " clash. */
const same = (a: string, b: string) =>
  a.trim().replace(/\s+/g, ' ').toLowerCase() === b.trim().replace(/\s+/g, ' ').toLowerCase()

/** One message per colour that has a problem: empty, longer than 24 characters, or the same name as another colour. */
export function validateLegend(draft: ColorLegend): LegendErrors {
  const errors: LegendErrors = {}
  for (const key of COLOR_KEYS) {
    const name = draft[key].trim()
    if (name.length === 0) errors[key] = 'Give this colour a name.'
    else if (name.length > LEGEND_NAME_MAX) errors[key] = `Use ${LEGEND_NAME_MAX} characters or fewer.`
    else if (COLOR_KEYS.some((other) => other !== key && same(draft[other], name)))
      errors[key] = 'Another colour already has this name.'
  }
  return errors
}

/** The draft with names tidied the way the server stores them. */
export const tidyLegend = (draft: ColorLegend): ColorLegend =>
  Object.fromEntries(COLOR_KEYS.map((key) => [key, draft[key].trim().replace(/\s+/g, ' ')])) as ColorLegend

export const legendChanged = (draft: ColorLegend, saved: ColorLegend) =>
  COLOR_KEYS.some((key) => draft[key].trim() !== saved[key])
