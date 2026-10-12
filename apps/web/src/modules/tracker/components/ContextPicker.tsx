import { Label, SelectField } from '@artha/design-system'
import { useId } from 'react'

import { ChapterField } from '~/modules/coverage'

import { ACTIVITY_OPTIONS, type ActivityType } from '../lib/types'

export interface PickerValue {
  subject_id: string | null
  chapter_id: string | null
  /** "All chapters" was chosen: the time belongs to the whole subject, so chapter_id stays null. */
  all_chapters?: boolean
  activity_type: ActivityType
}

/** A study timer can start only once a subject and a chapter (or "All chapters") are chosen. */
export function hasSubjectAndChapter(value: Pick<PickerValue, 'subject_id' | 'chapter_id' | 'all_chapters'>) {
  return Boolean(value.subject_id && (value.chapter_id || value.all_chapters))
}

interface Props {
  subjects: Array<{ id: string; name: string }>
  chapters: Array<{ id: string; name: string }>
  value: PickerValue
  onChange: (patch: Partial<PickerValue>) => void
  disabled?: boolean
  /** Options are still being fetched: the open menus show a loader instead of looking empty. */
  subjectsLoading?: boolean
  chaptersLoading?: boolean
}

/** What the time is for: subject, chapter and kind of study. All optional, so the timer never waits on a choice. */
export function ContextPicker({
  subjects,
  chapters,
  value,
  onChange,
  disabled,
  subjectsLoading,
  chaptersLoading,
}: Props) {
  const id = useId()
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-subject`}>Subject</Label>
        <SelectField
          id={`${id}-subject`}
          disabled={disabled}
          loading={subjectsLoading}
          loadingText="Loading subjects…"
          emptyText="No subjects yet. Choose your course first."
          value={value.subject_id ?? ''}
          onValueChange={(subjectId) =>
            onChange({ subject_id: subjectId || null, chapter_id: null, all_chapters: false })
          }
          options={[{ value: '', label: 'No subject' }, ...subjects.map((s) => ({ value: s.id, label: s.name }))]}
        />
      </div>
      <ChapterField
        id={`${id}-chapter`}
        disabled={disabled || !value.subject_id}
        loading={chaptersLoading}
        chapters={chapters}
        value={{ chapter_id: value.chapter_id, all_chapters: Boolean(value.all_chapters) }}
        unsetLabel="No chapter"
        onChange={onChange}
      />
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-activity`}>Activity</Label>
        <SelectField
          id={`${id}-activity`}
          disabled={disabled}
          value={value.activity_type}
          onValueChange={(activity) => onChange({ activity_type: activity as ActivityType })}
          options={ACTIVITY_OPTIONS}
        />
      </div>
    </div>
  )
}
