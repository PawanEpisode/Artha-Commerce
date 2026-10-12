import { storedChapterSelection } from '~/modules/coverage'

import type { PickerValue } from '../components/ContextPicker'

/** What a running timer or a logged session is for, as the picker shows it: a subject with no chapter reads "All chapters". */
export function storedPickerValue(ctx: Pick<PickerValue, 'subject_id' | 'chapter_id' | 'activity_type'>): PickerValue {
  return { ...ctx, ...storedChapterSelection(ctx.subject_id, ctx.chapter_id) }
}

/** A picker change as the API takes it: `all_chapters` is UI-only (the whole subject is `chapter_id: null`). */
export function contextPatch(patch: Partial<PickerValue>): Omit<Partial<PickerValue>, 'all_chapters'> {
  const { all_chapters: _ignored, ...rest } = patch
  void _ignored
  return rest
}
