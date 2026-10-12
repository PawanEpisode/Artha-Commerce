import { SelectField } from '@artha/design-system'

import { ALL_CHAPTERS, ALL_CHAPTERS_LABEL } from '~/modules/coverage'

import type { PickerOption, PickerState } from '../lib/chapter-link'

export interface ChapterFieldsProps {
  /** Prefix for the three field ids, so two pickers on one screen never share a label. */
  idPrefix: string
  state: PickerState
  onState: (change: Partial<PickerState>) => void
  subjects: readonly PickerOption[]
  chapters: readonly PickerOption[]
  topics: readonly PickerOption[]
  loadingSubjects?: boolean
  loadingChapters?: boolean
  loadingTopics?: boolean
  /** Offer "All chapters": the item belongs to the whole subject. Off where one chapter is required (page ranges, marks). */
  allowAll?: boolean
  /** The empty subject entry: "Choose a subject", or "No subject (Unfiled)" where leaving it empty is fine. */
  subjectBlank?: string
  /** Show the optional topic field once a chapter is chosen. */
  withTopic?: boolean
  disabled?: boolean
}

const toOptions = (items: readonly PickerOption[]) => items.map((i) => ({ value: i.id, label: i.name }))

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children}
    </div>
  )
}

/**
 * Subject, then Chapter (with "All chapters" where the whole subject is allowed), then an optional Topic. The subject list is
 * the student's own papers; changing it clears the chapter and topic (the reducer in `lib/chapter-link`).
 */
export function ChapterFields({
  idPrefix,
  state,
  onState,
  subjects,
  chapters,
  topics,
  loadingSubjects,
  loadingChapters,
  loadingTopics,
  allowAll = false,
  subjectBlank = 'Choose a subject',
  withTopic = true,
  disabled,
}: ChapterFieldsProps) {
  const chapterPicked = state.chapterId !== '' && state.chapterId !== ALL_CHAPTERS
  return (
    <div className="space-y-4">
      <Field id={`${idPrefix}-subject`} label="Subject">
        <SelectField
          id={`${idPrefix}-subject`}
          value={state.subjectId}
          disabled={disabled}
          loading={loadingSubjects}
          loadingText="Loading subjects…"
          emptyText="No subjects yet. Choose your course first."
          onValueChange={(subjectId) => onState({ subjectId })}
          options={[{ value: '', label: subjectBlank }, ...toOptions(subjects)]}
        />
      </Field>
      <Field id={`${idPrefix}-chapter`} label="Chapter">
        <SelectField
          id={`${idPrefix}-chapter`}
          value={state.chapterId}
          disabled={disabled || !state.subjectId}
          loading={loadingChapters}
          loadingText="Loading chapters…"
          emptyText="No chapters for this subject"
          onValueChange={(chapterId) => onState({ chapterId })}
          options={[
            { value: '', label: state.subjectId ? 'Choose a chapter' : 'Choose a subject first' },
            ...(allowAll && state.subjectId ? [{ value: ALL_CHAPTERS, label: ALL_CHAPTERS_LABEL }] : []),
            ...toOptions(chapters),
          ]}
        />
      </Field>
      {withTopic && chapterPicked && (loadingTopics || topics.length > 0) ? (
        <Field id={`${idPrefix}-topic`} label="Topic (optional)">
          <SelectField
            id={`${idPrefix}-topic`}
            value={state.topicId}
            disabled={disabled || loadingTopics}
            loading={loadingTopics}
            loadingText="Loading topics…"
            onValueChange={(topicId) => onState({ topicId })}
            options={[{ value: '', label: 'Whole chapter' }, ...toOptions(topics)]}
          />
        </Field>
      ) : null}
    </div>
  )
}
