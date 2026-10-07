import { Button, ChevronDown, ChevronUp, cn, Highlighter, Input, LoaderCircle, Search, X } from '@artha/design-system'
import { type KeyboardEvent, type Ref } from 'react'

export interface SearchResultView {
  page: number
  snippet: string
}

export type SearchStatus = 'idle' | 'searching' | 'done' | 'error'

export interface ReaderSearchPanelProps {
  query: string
  onQueryChange: (query: string) => void
  results: ReadonlyArray<SearchResultView>
  /** Index in `results` of the current hit, or -1. */
  activeIndex: number
  status: SearchStatus
  /** Pages scanned so far (local search), for the progress line. */
  progress?: { done: number; total: number } | null
  /** The list stopped at its limit: "50+ results". */
  truncated?: boolean
  /** An extra line, for example "Search covers 120 of 320 pages so far". */
  note?: string | null
  onNext: () => void
  onPrevious: () => void
  onPick: (index: number) => void
  onClose: () => void
  /** Offered when the annotation layer is on: highlights the current hit with the default colour. */
  onHighlight?: () => void
  inputRef?: Ref<HTMLInputElement>
}

/** The sentence announced and shown for the current state of a search. */
export function searchSummary(
  p: Pick<ReaderSearchPanelProps, 'query' | 'results' | 'status' | 'progress' | 'truncated' | 'activeIndex'>,
): string {
  if (p.query.trim().length < 2) return 'Type at least two letters.'
  if (p.status === 'error') return 'Search is not available right now.'
  const n = p.results.length
  if (p.status === 'searching' && n === 0)
    return p.progress ? `Searching… page ${p.progress.done} of ${p.progress.total}` : 'Searching…'
  if (n === 0) return 'No results.'
  const total = `${n}${p.truncated ? '+' : ''} ${n === 1 && !p.truncated ? 'result' : 'results'}`
  return p.activeIndex >= 0 ? `Result ${p.activeIndex + 1} of ${total}` : total
}

/**
 * In-document search, docked under the top bar so the page and its highlights stay visible while typing. The count is a
 * live region; Enter goes to the next hit, Shift + Enter to the previous one, Escape closes. The list shows the first 50.
 */
export function ReaderSearchPanel({
  query,
  onQueryChange,
  results,
  activeIndex,
  status,
  progress,
  truncated,
  note,
  onNext,
  onPrevious,
  onPick,
  onClose,
  onHighlight,
  inputRef,
}: ReaderSearchPanelProps) {
  const summary = searchSummary({ query, results, status, progress, truncated, activeIndex })
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (e.shiftKey) onPrevious()
      else onNext()
    } else if (e.altKey && e.key.toLowerCase() === 'h' && onHighlight && activeIndex >= 0) {
      e.preventDefault()
      onHighlight()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      onClose()
    }
  }
  return (
    <section
      role="search"
      aria-label="Search in this PDF"
      data-slot="reader-search"
      className="grid gap-2 rounded-xl border border-border bg-card p-2 text-card-foreground shadow-lift"
    >
      <div className="flex items-center gap-1">
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            ref={inputRef}
            type="search"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search this PDF"
            aria-label="Search this PDF"
            autoComplete="off"
            enterKeyHint="search"
            className="h-11 pl-9"
          />
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-11"
          onClick={onPrevious}
          disabled={results.length === 0}
          aria-label="Previous result"
        >
          <ChevronUp aria-hidden />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-11"
          onClick={onNext}
          disabled={results.length === 0}
          aria-label="Next result"
        >
          <ChevronDown aria-hidden />
        </Button>
        {onHighlight ? (
          <Button
            variant="ghost"
            size="icon"
            className="size-11"
            onClick={onHighlight}
            disabled={activeIndex < 0}
            aria-label="Highlight this result"
            aria-keyshortcuts="Alt+H"
            title="Highlight this result"
          >
            <Highlighter aria-hidden />
          </Button>
        ) : null}
        <Button variant="ghost" size="icon" className="size-11" onClick={onClose} aria-label="Close search">
          <X aria-hidden />
        </Button>
      </div>
      <p role="status" aria-live="polite" className="flex items-center gap-2 px-1 text-sm text-muted-foreground">
        {status === 'searching' ? (
          <LoaderCircle className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
        ) : null}
        <span>{summary}</span>
      </p>
      {note ? <p className="px-1 text-xs text-muted-foreground">{note}</p> : null}
      {results.length > 0 ? (
        <ol aria-label="Search results" className="max-h-[40dvh] overflow-y-auto">
          {results.slice(0, 50).map((hit, i) => (
            <li key={`${hit.page}-${i}`}>
              <button
                type="button"
                onClick={() => onPick(i)}
                aria-current={i === activeIndex ? 'true' : undefined}
                className={cn(
                  'flex min-h-11 w-full items-start gap-3 rounded-lg px-2 py-2 text-left text-sm outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40',
                  i === activeIndex && 'bg-secondary',
                )}
              >
                <span className="w-10 shrink-0 pt-0.5 text-xs font-semibold text-muted-foreground tabular-nums">
                  p. {hit.page}
                </span>
                <span className="min-w-0 break-words">{hit.snippet}</span>
              </button>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  )
}
