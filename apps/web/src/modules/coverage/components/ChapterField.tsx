import { Label, SelectField } from '@artha/design-system'

import { type ChapterSelection, chapterSelectionOf, chapterSelectValue, isChapterUnset } from '../lib/chapterSelection'
import { ALL_CHAPTERS, ALL_CHAPTERS_LABEL } from '../lib/subjects'

interface Props {
  id: string
  chapters: Array<{ id: string; name: string }>
  value: ChapterSelection
  onChange: (next: ChapterSelection) => void
  label?: string
  /** Shown while nothing is chosen yet; leave out when "All chapters" is the natural default (a filter). */
  unsetLabel?: string
  disabled?: boolean
  loading?: boolean
}

/** The Chapter select that sits next to a Subject select: every chapter of it, plus "All chapters" (the whole subject). */
export function ChapterField({
  id,
  chapters,
  value,
  onChange,
  label = 'Chapter',
  unsetLabel,
  disabled,
  loading,
}: Props) {
  const unset = isChapterUnset(value)
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <SelectField
        id={id}
        disabled={disabled}
        loading={loading}
        loadingText="Loading chapters…"
        emptyText="No chapters for this subject"
        value={chapterSelectValue(value)}
        onValueChange={(v) => onChange(chapterSelectionOf(v))}
        options={[
          ...(unset && unsetLabel ? [{ value: '', label: unsetLabel }] : []),
          { value: ALL_CHAPTERS, label: ALL_CHAPTERS_LABEL },
          ...chapters.map((c) => ({ value: c.id, label: c.name })),
        ]}
      />
    </div>
  )
}
