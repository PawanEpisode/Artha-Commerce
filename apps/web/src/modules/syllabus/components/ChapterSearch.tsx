import { TextField } from '@artha/design-system'

import { pluralize } from '../lib/format'

interface Props {
  value: string
  onChange: (value: string) => void
  /** Chapters matching the search, and all chapters of the paper. */
  shown: number
  total: number
}

/** Find a chapter by name inside a long paper. Callers only render it when the paper has enough chapters to need it. */
export function ChapterSearch({ value, onChange, shown, total }: Props) {
  return (
    <TextField
      label="Find a chapter"
      type="search"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      hint={value.trim() ? `${pluralize(shown, 'chapter')} of ${total} match` : undefined}
    />
  )
}
