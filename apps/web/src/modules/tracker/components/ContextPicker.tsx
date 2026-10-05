import { Label, Select } from '@artha/design-system'
import { useId } from 'react'

import { ACTIVITY_OPTIONS, type ActivityType } from '../lib/types'

export interface PickerValue {
  subject_id: string | null
  chapter_id: string | null
  activity_type: ActivityType
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
        <Select
          id={`${id}-subject`}
          disabled={disabled}
          value={value.subject_id ?? ''}
          onChange={(e) => onChange({ subject_id: e.target.value || null, chapter_id: null })}
        >
          <option value="">No subject</option>
          {subjects.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-chapter`}>Chapter</Label>
        <Select
          id={`${id}-chapter`}
          disabled={disabled || !value.subject_id}
          value={value.chapter_id ?? ''}
          onChange={(e) => onChange({ chapter_id: e.target.value || null })}
        >
          <option value="">No chapter</option>
          {chapters.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-activity`}>Activity</Label>
        <Select
          id={`${id}-activity`}
          disabled={disabled}
          value={value.activity_type}
          onChange={(e) => onChange({ activity_type: e.target.value as ActivityType })}
        >
          {ACTIVITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </div>
    </div>
  )
}
