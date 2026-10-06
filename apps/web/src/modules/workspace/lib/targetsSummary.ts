import { presetLabel, type TargetPreset, type Targets, type TargetsPreset } from '~/modules/coverage'

export interface TargetRow {
  label: string
  /** Count per chapter, or null when the student does not track this activity (target 0). */
  count: number | null
}

const plural = (n: number, one: string, many: string) => (n === 1 ? one : many)

/** The three targets as rows; 0 means "not tracked" and is shown as such, never as "0 per chapter". */
export function targetRows(t: Targets): TargetRow[] {
  return [
    {
      label: plural(t.practice_sets, 'practice set', 'practice sets'),
      count: t.practice_sets > 0 ? t.practice_sets : null,
    },
    { label: plural(t.revisions, 'revision', 'revisions'), count: t.revisions > 0 ? t.revisions : null },
    { label: plural(t.mocks, 'mock', 'mocks'), count: t.mocks > 0 ? t.mocks : null },
  ]
}

/** "Standard" or "Custom". */
export const targetsHeading = (key: TargetsPreset, presets?: ReadonlyArray<TargetPreset>) =>
  `${presetLabel(key, presets)} targets`
