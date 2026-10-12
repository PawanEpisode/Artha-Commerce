import type { DiffSegment } from '../lib/wordDiff'

/**
 * A text with its changed words marked. Colour is never the only signal: added words are underlined, removed words struck
 * through, and a screen reader hears "added" and "removed" before each changed run.
 */
export function WordDiff({ segments, label }: { segments: DiffSegment[]; label: string }) {
  return (
    <p className="rounded-lg bg-muted/50 p-2 text-sm break-words" aria-label={label}>
      {segments.map((s, i) =>
        s.kind === 'same' ? (
          <span key={i}>{s.text}</span>
        ) : s.kind === 'added' ? (
          <ins
            key={i}
            className="rounded-sm bg-primary/10 text-foreground underline decoration-primary underline-offset-2"
          >
            <span className="sr-only">added: </span>
            {s.text}
          </ins>
        ) : (
          <del key={i} className="text-muted-foreground line-through">
            <span className="sr-only">removed: </span>
            {s.text}
          </del>
        ),
      )}
    </p>
  )
}
