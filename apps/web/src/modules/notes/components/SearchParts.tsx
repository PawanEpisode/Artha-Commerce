import { Button, Card, History, Search, X } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { linkLabel } from '../lib/chapter-link'
import { relativeTime } from '../lib/format'
import { splitHighlight } from '../lib/search-query'
import type { SearchHit } from '../lib/types'

export function SearchBox({
  value,
  onChange,
  onSubmit,
  busy,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  busy?: boolean
}) {
  return (
    <form
      role="search"
      aria-label="Search notes"
      className="flex gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <div className="grid min-w-0 flex-1 gap-2">
        <label htmlFor="notes-search" className="sr-only">
          Search your notes
        </label>
        <input
          id="notes-search"
          type="search"
          value={value}
          maxLength={200}
          autoComplete="off"
          enterKeyHint="search"
          placeholder="Search your notes, for example 17(5) or ITC"
          onChange={(e) => onChange(e.target.value)}
          className="h-11 w-full rounded-lg border border-input bg-card px-3.5 text-base outline-none placeholder:text-muted-foreground focus-visible:ring-[3px] focus-visible:ring-ring/40 md:text-sm"
        />
      </div>
      <Button type="submit" disabled={busy || value.trim() === ''}>
        <Search aria-hidden /> Search
      </Button>
    </form>
  )
}

export function RecentSearches({
  items,
  onPick,
  onClear,
}: {
  items: readonly string[]
  onPick: (query: string) => void
  onClear: () => void
}) {
  if (items.length === 0) return null
  return (
    <section aria-label="Recent searches" className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-muted-foreground">Recent searches (kept on this device)</h2>
        <Button variant="ghost" size="sm" onClick={onClear}>
          <X aria-hidden /> Clear
        </Button>
      </div>
      <ul className="flex flex-wrap gap-2">
        {items.map((q) => (
          <li key={q}>
            <Button variant="outline" className="max-w-full" onClick={() => onPick(q)}>
              <History aria-hidden />
              <span className="min-w-0 truncate">{q}</span>
            </Button>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Highlighted({ text, query }: { text: string; query: string }) {
  return (
    <>
      {splitHighlight(text, query).map((piece, index) =>
        piece.match ? (
          <mark key={index} className="rounded-sm bg-highlight/30 px-0.5 text-foreground">
            {piece.text}
          </mark>
        ) : (
          <span key={index}>{piece.text}</span>
        ),
      )}
    </>
  )
}

export function SearchHitList({
  hits,
  query,
  onOpen,
}: {
  hits: readonly SearchHit[]
  query: string
  onOpen?: () => void
}) {
  return (
    <ul aria-label="Search results" className="space-y-3">
      {hits.map((hit) => (
        <li key={hit.id}>
          <Card className="space-y-1 p-4">
            <h3 className="font-display text-lg leading-snug font-bold break-words">
              <Link
                to="/app/notes/n/$noteId"
                params={{ noteId: hit.id }}
                onClick={onOpen}
                className="underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-[3px] focus-visible:ring-ring/40"
              >
                <Highlighted text={hit.title.trim() || 'Untitled note'} query={query} />
              </Link>
            </h3>
            {hit.snippet ? (
              <p className="line-clamp-3 text-sm break-words text-muted-foreground">
                <Highlighted text={hit.snippet} query={query} />
              </p>
            ) : null}
            <p className="text-xs text-muted-foreground">
              {linkLabel(hit.link)}. <time dateTime={hit.updated_at}>{relativeTime(hit.updated_at)}</time>
            </p>
          </Card>
        </li>
      ))}
    </ul>
  )
}
