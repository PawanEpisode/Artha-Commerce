import { Button, FilterChip, SegmentedControl, SelectField, TextField } from '@artha/design-system'

import {
  activeFilters,
  type FilterKey,
  type NoteFilterSearch,
  type NoteTab,
  tabOf,
  withoutFilter,
} from '../lib/filter-schema'
import { formatDate } from '../lib/format'
import type { Tag } from '../lib/types'

const TABS: ReadonlyArray<{ value: NoteTab; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'notes', label: 'Notes' },
]

interface FilterBarProps {
  search: NoteFilterSearch
  tags: readonly Tag[]
  /** Topics of the chapter, when the page is a chapter. */
  topics?: ReadonlyArray<{ key: string; name: string }>
  onChange: (next: NoteFilterSearch) => void
}

function describe(key: FilterKey, search: NoteFilterSearch, tags: readonly Tag[], topics: FilterBarProps['topics']) {
  switch (key) {
    case 'tag':
      return `Tag: ${tags.find((t) => t.id === search.tag)?.name ?? 'unknown'}`
    case 'from':
      return `From ${formatDate(search.from)}`
    case 'to':
      return `Until ${formatDate(search.to)}`
    case 'topic':
      return `Topic: ${topics?.find((t) => t.key === search.topic)?.name ?? search.topic}`
    case 'color':
      return `Colour: ${search.color}`
    case 'doc':
      return 'One document'
  }
}

/**
 * The filters of a subject or chapter view. Everything it changes goes into the URL (via `onChange`), and every active
 * filter shows as a chip that removes itself, so a view is never narrowed without saying so.
 */
export function FilterBar({ search, tags, topics, onChange }: FilterBarProps) {
  const active = activeFilters(search)
  return (
    <section aria-label="Filters" className="space-y-3">
      <SegmentedControl
        label="What to show"
        value={tabOf(search)}
        options={TABS}
        onValueChange={(tab) => onChange({ ...search, tab, cursor: undefined })}
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="grid gap-2">
          <label htmlFor="notes-filter-tag" className="text-sm font-medium">
            Tag
          </label>
          <SelectField
            id="notes-filter-tag"
            value={search.tag ?? ''}
            onValueChange={(tag) => onChange({ ...search, tag: tag || undefined, cursor: undefined })}
            options={[{ value: '', label: 'Any tag' }, ...tags.map((t) => ({ value: t.id, label: t.name }))]}
          />
        </div>
        {topics && topics.length > 0 ? (
          <div className="grid gap-2">
            <label htmlFor="notes-filter-topic" className="text-sm font-medium">
              Topic
            </label>
            <SelectField
              id="notes-filter-topic"
              value={search.topic ?? ''}
              onValueChange={(topic) => onChange({ ...search, topic: topic || undefined, cursor: undefined })}
              options={[{ value: '', label: 'Any topic' }, ...topics.map((t) => ({ value: t.key, label: t.name }))]}
            />
          </div>
        ) : null}
        <TextField
          label="From"
          type="date"
          value={search.from ?? ''}
          onChange={(e) => onChange({ ...search, from: e.target.value || undefined, cursor: undefined })}
        />
        <TextField
          label="To"
          type="date"
          value={search.to ?? ''}
          onChange={(e) => onChange({ ...search, to: e.target.value || undefined, cursor: undefined })}
        />
      </div>
      {active.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          {active.map((key) => {
            const text = describe(key, search, tags, topics)
            return (
              <FilterChip
                key={key}
                removeLabel={`Remove filter ${text}`}
                onRemove={() => onChange(withoutFilter(search, key))}
              >
                {text}
              </FilterChip>
            )
          })}
          <Button variant="ghost" size="sm" onClick={() => onChange({ tab: search.tab })}>
            Clear all
          </Button>
        </div>
      ) : null}
    </section>
  )
}
