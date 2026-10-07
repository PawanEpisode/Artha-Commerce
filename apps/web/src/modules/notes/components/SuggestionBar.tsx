import { Button, Sparkles } from '@artha/design-system'

import type { ChapterSuggestion } from '../lib/types'

interface SuggestionBarProps {
  suggestions: readonly ChapterSuggestion[]
  busy?: boolean
  onPick: (suggestion: ChapterSuggestion) => void
  /** "Choose another chapter": opens the full picker. */
  onOther: () => void
}

/** One tap filing for an unfiled note: up to three chapters from a plain text match (no AI), then the full picker. */
export function SuggestionBar({ suggestions, busy, onPick, onOther }: SuggestionBarProps) {
  return (
    <div role="group" aria-label="Suggested chapters" className="flex flex-wrap items-center gap-2 pl-1">
      {suggestions.length > 0 ? (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
          <Sparkles aria-hidden className="size-3.5" /> Looks like
        </span>
      ) : null}
      {suggestions.map((s) => (
        <Button
          key={s.chapter_id}
          size="sm"
          variant="secondary"
          className="h-auto min-h-11 max-w-full py-1.5 text-left whitespace-normal"
          disabled={busy}
          onClick={() => onPick(s)}
        >
          <span className="min-w-0 break-words">
            {s.chapter_name} <span className="text-xs opacity-80">({s.subject_name})</span>
          </span>
        </Button>
      ))}
      <Button size="sm" variant="outline" disabled={busy} onClick={onOther}>
        Choose a chapter
      </Button>
    </div>
  )
}
