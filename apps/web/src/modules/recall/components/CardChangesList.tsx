import { Alert, Badge, Button, Skeleton } from '@artha/design-system'
import { useState } from 'react'

import { changeKindLabel, dayText, resetReasonLabel, versionStatus, waitingText } from '../lib/history'
import type { CardChanges } from '../lib/schemas'
import { diffWords, hasWordChange } from '../lib/wordDiff'
import { LoadError } from './RecallShell'
import { WordDiff } from './WordDiff'

interface Props {
  changes: CardChanges | undefined
  loading: boolean
  failed: boolean
  onRetry: () => void
}

/** The versions of a card's text, newest first, with the one she is on marked, and the times it came back for a re-check. */
export function CardChangesList({ changes, loading, failed, onRetry }: Props) {
  const [shown, setShown] = useState<number | null>(null)
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
    <div className="space-y-3">
      {waiting ? <Alert variant="info">{waiting}</Alert> : null}
      <ol className="space-y-2" aria-label="Versions of this card">
        {changes.versions.map((v, index) => {
          const older = changes.versions[index + 1]
          const segments = older && v.text && older.text ? diffWords(older.text, v.text) : []
          const canCompare = hasWordChange(segments)
          const olderNo = older?.version_no
          const open = shown === v.version_no
          return (
            <li key={v.version_no} className="space-y-1 rounded-lg border border-border bg-card p-2.5 text-[13px]">
              <p className="flex flex-wrap items-center gap-2 font-semibold">
                Version {v.version_no}
                <Badge variant={v.current ? 'accent' : 'outline'}>{versionStatus(v)}</Badge>
              </p>
              <p className="text-muted-foreground">
                {changeKindLabel(v.change_kind)}
                {v.at ? ` · ${dayText(v.at)}` : ''}
              </p>
              {v.change_note ? <p className="break-words">{v.change_note}</p> : null}
              {open && canCompare ? (
                <WordDiff segments={segments} label={`Words changed since version ${olderNo ?? ''}`} />
              ) : v.text ? (
                <p className="break-words text-muted-foreground">{v.text}</p>
              ) : null}
              {canCompare ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-expanded={open}
                  onClick={() => setShown(open ? null : v.version_no)}
                >
                  {open ? 'Hide the changed words' : `Show what changed since version ${olderNo ?? ''}`}
                </Button>
              ) : null}
            </li>
          )
        })}
      </ol>
      {changes.resets.length > 0 ? (
        <section aria-label="Times this card came back" className="space-y-1">
          <h3 className="text-[13px] font-semibold">Times it came back for a re-check</h3>
          <ul className="list-disc space-y-1 pl-5 text-[13px] text-muted-foreground">
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
