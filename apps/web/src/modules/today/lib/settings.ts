/** Words and rules of the Today settings page (PRD 7.3 "Settings"). Pure. */
import type { TodaySettings } from './types'

/** What "Reset to defaults" saves: automatic budget and focus, nothing hidden, tomorrow and celebration on, lite follows the network. */
export const DEFAULT_SETTINGS: TodaySettings = {
  minutes_per_day: null,
  focus_papers: null,
  disabled_kinds: [],
  show_tomorrow: true,
  celebrate: true,
  lite_mode: 'auto',
}

/** Presets of "minutes per day"; `null` is automatic (from your exam date and study hours). */
export const MINUTE_PRESETS = [30, 60, 90, 120] as const

export const FOCUS_OPTIONS = ['auto', '1', '2', '3', '4'] as const

/** The kinds of task Today can offer today, in plain words. A kind this table does not know is shown by a readable form of its name. */
const KIND_LABELS: Record<string, string> = {
  revise_chapter: 'Chapter revisions that are due',
  next_topic: 'The next topics in a chapter',
  next_chapter: 'The next chapter to start',
  recall_cards: 'Flashcards that are due',
  forgotten_cards: 'Cards you have forgotten',
  recheck: 'Re-check after an amendment',
}

export const KNOWN_KINDS = Object.keys(KIND_LABELS)

export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())
}

/** The kinds the page lists: the ones we know, plus any the student already hid that we do not (so they can switch them back on). */
export const listedKinds = (hidden: readonly string[]) => [
  ...KNOWN_KINDS,
  ...hidden.filter((k) => !KNOWN_KINDS.includes(k)),
]

/** The setting names whose value differs, for the `today_settings_changed` event (names only, never values). */
export function changedKeys(before: TodaySettings, after: Partial<TodaySettings>): string[] {
  return (Object.keys(after) as Array<keyof TodaySettings>).filter(
    (key) => JSON.stringify(before[key]) !== JSON.stringify(after[key]),
  )
}

export const focusValue = (value: number | null) => (value === null ? 'auto' : String(value))
export const focusFromValue = (value: string) => (value === 'auto' ? null : Number(value))
