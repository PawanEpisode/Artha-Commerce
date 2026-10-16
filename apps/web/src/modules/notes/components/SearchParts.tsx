import {
  Button,
  DataTable,
  History,
  Search,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  X,
} from '@artha/design-system'
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
      className="flex max-w-2xl gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <div className="grid min-w-0 flex-1">
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
          className="h-8 w-full rounded-md border border-input bg-card px-2.5 text-[13px] outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/50 pointer-coarse:h-11 pointer-coarse:text-base"
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
        <h2 className="text-xs font-semibold text-muted-foreground">Recent searches (kept on this device)</h2>
        <Button variant="ghost" size="sm" onClick={onClear}>
          <X aria-hidden /> Clear
        </Button>
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {items.map((q) => (
          <li key={q}>
            <Button variant="outline" size="sm" className="max-w-full" onClick={() => onPick(q)}>
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
    <DataTable aria-label="Search results">
      <TableHeader>
        <TableRow>
          <TableHead>Note</TableHead>
          <TableHead className="hidden md:table-cell">Filed under</TableHead>
          <TableHead className="text-right">Updated</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {hits.map((hit) => (
          <TableRow key={hit.id}>
            <TableCell className="min-w-56 py-2 whitespace-normal">
              <Link
                to="/app/notes/n/$noteId"
                params={{ noteId: hit.id }}
                onClick={onOpen}
                className="font-medium break-words underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                <Highlighted text={hit.title.trim() || 'Untitled note'} query={query} />
              </Link>
              {hit.snippet ? (
                <p className="line-clamp-2 text-xs break-words text-muted-foreground">
                  <Highlighted text={hit.snippet} query={query} />
                </p>
              ) : null}
            </TableCell>
            <TableCell className="hidden max-w-64 text-xs text-muted-foreground md:table-cell">
              <span className="line-clamp-2 break-words">{linkLabel(hit.link)}</span>
            </TableCell>
            <TableCell className="text-right text-xs whitespace-nowrap text-muted-foreground tabular-nums">
              <time dateTime={hit.updated_at}>{relativeTime(hit.updated_at)}</time>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </DataTable>
  )
}
