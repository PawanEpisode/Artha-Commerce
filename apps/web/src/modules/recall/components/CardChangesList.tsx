import { Alert, Badge, Skeleton } from '@artha/design-system'

import { changeKindLabel, dayText, resetReasonLabel, versionStatus, waitingText } from '../lib/history'
import type { CardChanges } from '../lib/schemas'
import { LoadError } from './RecallShell'

interface Props {
  changes: CardChanges | undefined
  loading: boolean
  failed: boolean
  onRetry: () => void
}

/** The versions of a card's text, newest first, with the one she is on marked, and the times it came back for a re-check. */
export function CardChangesList({ changes, loading, failed, onRetry }: Props) {
  if (loading) {
    return (
      <div aria-busy="true">
        <span className="sr-only" role="status">
          Loading what changed…
        </span>
        <Skeleton className="h-20 w-full" />
      </div>
    )
  }
  if (failed || !changes) return <LoadError what="what changed" onRetry={onRetry} />
  const waiting = waitingText(changes.waiting)
  return (
    <div className="space-y-4">
      {waiting ? <Alert variant="info">{waiting}</Alert> : null}
      <ol className="space-y-3" aria-label="Versions of this card">
        {changes.versions.map((v) => (
          <li key={v.version_no} className="space-y-1 rounded-xl border border-border bg-card p-3 text-sm">
            <p className="flex flex-wrap items-center gap-2 font-semibold">
              Version {v.version_no}
              <Badge variant={v.current ? 'accent' : 'outline'}>{versionStatus(v)}</Badge>
            </p>
            <p className="text-muted-foreground">
              {changeKindLabel(v.change_kind)}
              {v.at ? ` · ${dayText(v.at)}` : ''}
            </p>
            {v.change_note ? <p className="break-words">{v.change_note}</p> : null}
            {v.text ? <p className="break-words text-muted-foreground">{v.text}</p> : null}
          </li>
        ))}
      </ol>
      {changes.resets.length > 0 ? (
        <section aria-label="Times this card came back" className="space-y-1">
          <h3 className="text-sm font-semibold">Times it came back for a re-check</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {changes.resets.map((r) => (
              <li key={`${r.at}-${r.reason}`}>
                {dayText(r.at)}: {resetReasonLabel(r.reason)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}
