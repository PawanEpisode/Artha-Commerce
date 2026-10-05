import { Label, SelectField } from '@artha/design-system'
import { useId } from 'react'

import { ACTIVITY_OPTIONS, type ActivityType } from '../lib/types'

export interface PickerValue {
  subject_id: string | null
  chapter_id: string | null
  activity_type: ActivityType
}

/** A study timer can start only once both a subject and a chapter are chosen. */
export function hasSubjectAndChapter(value: Pick<PickerValue, 'subject_id' | 'chapter_id'>) {
  return Boolean(value.subject_id && value.chapter_id)
}

interface Props {
  subjects: Array<{ id: string; name: string }>
  chapters: Array<{ id: string; name: string }>
  value: PickerValue
  onChange: (patch: Partial<PickerValue>) => void
  disabled?: boolean
}

/** What the time is for: subject, chapter and kind of study. All optional, so the timer never waits on a choice. */
export function ContextPicker({ subjects, chapters, value, onChange, disabled }: Props) {
  const id = useId()
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-subject`}>Subject</Label>
        <SelectField
          id={`${id}-subject`}
          disabled={disabled}
          value={value.subject_id ?? ''}
          onValueChange={(subjectId) => onChange({ subject_id: subjectId || null, chapter_id: null })}
          options={[{ value: '', label: 'No subject' }, ...subjects.map((s) => ({ value: s.id, label: s.name }))]}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-chapter`}>Chapter</Label>
        <SelectField
          id={`${id}-chapter`}
          disabled={disabled || !value.subject_id}
          value={value.chapter_id ?? ''}
          onValueChange={(chapterId) => onChange({ chapter_id: chapterId || null })}
          options={[{ value: '', label: 'No chapter' }, ...chapters.map((c) => ({ value: c.id, label: c.name }))]}
        />
      </div>
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
