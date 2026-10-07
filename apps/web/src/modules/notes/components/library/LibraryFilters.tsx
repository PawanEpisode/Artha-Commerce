import { Button, FilterChip, ListFilter, Search, SegmentedControl, SelectField } from '@artha/design-system'
import { useEffect, useState } from 'react'

import {
  activeLibraryFilters,
  LIBRARY_STATUSES,
  type LibraryFilterKey,
  type LibrarySearch,
  SOURCE_KINDS,
  SOURCE_LABEL,
  STATUS_LABEL,
  withoutLibraryFilter,
} from '../../lib/library-schema'
import type { Tag } from '../../lib/types'

interface Option {
  value: string
  label: string
}

interface LibraryFiltersProps {
  search: LibrarySearch
  subjects: readonly Option[]
  chapters: readonly Option[]
  tags: readonly Tag[]
  onChange: (next: LibrarySearch) => void
  /** Milliseconds the search box waits after the last key before it filters. */
  debounceMs?: number
}

function describe(
  key: LibraryFilterKey,
  search: LibrarySearch,
  props: Pick<LibraryFiltersProps, 'subjects' | 'chapters' | 'tags'>,
) {
  switch (key) {
    case 'subject':
      return `Subject: ${props.subjects.find((s) => s.value === search.subject)?.label ?? search.subject}`
    case 'chapter':
      return `Chapter: ${props.chapters.find((c) => c.value === search.chapter)?.label ?? search.chapter}`
    case 'status':
      return `Status: ${search.status ? STATUS_LABEL[search.status] : ''}`
    case 'tag':
      return `Tag: ${props.tags.find((t) => t.id === search.tag)?.name ?? 'unknown'}`
    case 'source':
      return `From: ${search.source ? SOURCE_LABEL[search.source] : ''}`
    case 'q':
      return `Title: ${search.q}`
  }
}

/**
 * Search by title, sort, and a "Filters" disclosure (subject, chapter, tag, status, where it is from). Every active filter
 * shows as a removable chip, so the list is never narrowed silently. The search box filters as you type, after a short pause.
 */
export function LibraryFilters({ search, subjects, chapters, tags, onChange, debounceMs = 250 }: LibraryFiltersProps) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState(search.q ?? '')
  useEffect(() => setText(search.q ?? ''), [search.q])
  useEffect(() => {
    if (text.trim() === (search.q ?? '')) return
    const timer = setTimeout(() => onChange({ ...search, q: text.trim() || undefined }), debounceMs)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text])

  const active = activeLibraryFilters(search).filter((k) => k !== 'q')
  const set = (patch: Partial<LibrarySearch>) => onChange({ ...search, ...patch })

  return (
    <section aria-label="Find a PDF" className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className="relative min-w-0 flex-1 basis-56">
          <label htmlFor="library-q" className="sr-only">
            Search your PDFs by title
          </label>
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <input
            id="library-q"
            type="search"
            value={text}
            maxLength={200}
            autoComplete="off"
            placeholder="Search your PDFs by title"
            onChange={(e) => setText(e.target.value)}
            className="h-11 w-full rounded-lg border border-input bg-card pr-3 pl-9 text-base outline-none placeholder:text-muted-foreground focus-visible:ring-[3px] focus-visible:ring-ring/40 md:text-sm"
          />
        </div>
        <SegmentedControl
          label="Sort by"
          value={search.sort ?? 'recent'}
          options={[
            { value: 'recent', label: 'Recent' },
            { value: 'title', label: 'Title' },
          ]}
          onValueChange={(sort) => set({ sort })}
        />
        <Button
          variant="outline"
          aria-expanded={open}
          aria-controls="library-filter-panel"
          onClick={() => setOpen((v) => !v)}
        >
          <ListFilter aria-hidden /> Filters{active.length > 0 ? ` (${active.length})` : ''}
        </Button>
      </div>

      {open ? (
        <div
          id="library-filter-panel"
          className="grid gap-3 rounded-xl border border-border bg-card p-3 sm:grid-cols-2 lg:grid-cols-3"
        >
          <Field id="lib-subject" label="Subject">
            <SelectField
              id="lib-subject"
              value={search.subject ?? ''}
              onValueChange={(subject) => set({ subject: subject || undefined, chapter: undefined })}
              options={[{ value: '', label: 'Any subject' }, ...subjects]}
            />
          </Field>
          <Field id="lib-chapter" label="Chapter">
            <SelectField
              id="lib-chapter"
              value={search.chapter ?? ''}
              disabled={!search.subject}
              onValueChange={(chapter) => set({ chapter: chapter || undefined })}
              options={[{ value: '', label: search.subject ? 'Any chapter' : 'Choose a subject first' }, ...chapters]}
            />
          </Field>
          <Field id="lib-tag" label="Tag">
            <SelectField
              id="lib-tag"
              value={search.tag ?? ''}
              onValueChange={(tag) => set({ tag: tag || undefined })}
              options={[{ value: '', label: 'Any tag' }, ...tags.map((t) => ({ value: t.id, label: t.name }))]}
            />
          </Field>
          <Field id="lib-status" label="Status">
            <SelectField
              id="lib-status"
              value={search.status ?? ''}
              onValueChange={(status) => set({ status: (status || undefined) as LibrarySearch['status'] })}
              options={[
                { value: '', label: 'Any status' },
                ...LIBRARY_STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] })),
              ]}
            />
          </Field>
          <Field id="lib-source" label="Where it is from">
            <SelectField
              id="lib-source"
              value={search.source ?? ''}
              onValueChange={(source) => set({ source: (source || undefined) as LibrarySearch['source'] })}
              options={[
                { value: '', label: 'Anywhere' },
                ...SOURCE_KINDS.map((s) => ({ value: s, label: SOURCE_LABEL[s] })),
              ]}
            />
          </Field>
        </div>
      ) : null}

      {active.length > 0 || search.q ? (
        <div className="flex flex-wrap items-center gap-2">
          {[...active, ...(search.q ? (['q'] as const) : [])].map((key) => {
            const text = describe(key, search, { subjects, chapters, tags })
            return (
              <FilterChip
                key={key}
                removeLabel={`Remove filter ${text}`}
                onRemove={() => onChange(withoutLibraryFilter(search, key))}
              >
                {text}
              </FilterChip>
            )
          })}
          <Button variant="ghost" size="sm" onClick={() => onChange({ sort: search.sort })}>
            Clear all
          </Button>
        </div>
      ) : null}
    </section>
  )
}

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
