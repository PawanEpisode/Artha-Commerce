import {
  Button,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@artha/design-system'

import { diffLines, hasChanges } from '../lib/conflict'
import { formatDate, formatTime } from '../lib/format'
import type { Resolution } from '../lib/types'

interface ConflictSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  theirs: { title: string; body_md: string; updated_at: string }
  mine: { title: string; body: string }
  deviceLabel?: string
  busy: boolean
  /** What the student sees changed: "note" (default) or "mark". */
  noun?: string
  onResolve: (resolution: Resolution) => void
}

const MARK = { same: '  ', theirs: 'Theirs', mine: 'Yours' } as const

/**
 * Two versions of one note: the one saved from another device and the one you wrote. Shows exactly which lines
 * differ (with words, not colour only) and lets the student keep mine, keep theirs, or keep both. Nothing is lost
 * until a choice is made, and "Keep both" loses nothing at all.
 */
export function ConflictSheet({
  open,
  onOpenChange,
  theirs,
  mine,
  deviceLabel,
  busy,
  noun = 'note',
  onResolve,
}: ConflictSheetProps) {
  const lines = diffLines(theirs.body_md, mine.body)
  const different = hasChanges(lines)
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[92dvh] overflow-y-auto sm:mx-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>This {noun} changed somewhere else</SheetTitle>
          <SheetDescription>
            {deviceLabel ? `${deviceLabel} saved` : 'Another device saved'} a version on {formatDate(theirs.updated_at)}{' '}
            at {formatTime(theirs.updated_at)} while you were editing. Choose what to keep.
          </SheetDescription>
        </SheetHeader>
        {theirs.title !== mine.title ? (
          <p className="mb-3 text-sm">
            <span className="font-semibold">Title:</span> theirs is &ldquo;{theirs.title || 'Untitled'}&rdquo;, yours is
            &ldquo;{mine.title || 'Untitled'}&rdquo;.
          </p>
        ) : null}
        <div
          role="region"
          aria-label="Differences between the two versions"
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scrollable region must be reachable by keyboard
          tabIndex={0}
          className="max-h-72 overflow-auto rounded-lg border bg-card p-2 font-mono text-xs leading-relaxed outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
        >
          {!different ? <p className="p-2 text-muted-foreground">The text is the same in both versions.</p> : null}
          {lines.map((line, index) => (
            <div
              key={index}
              data-kind={line.kind}
              className={
                line.kind === 'same'
                  ? 'flex gap-2 px-2 py-0.5 text-muted-foreground'
                  : line.kind === 'mine'
                    ? 'flex gap-2 border-l-4 border-primary bg-secondary px-2 py-0.5'
                    : 'flex gap-2 border-l-4 border-warning-border bg-warning-bg px-2 py-0.5 text-warning-fg'
              }
            >
              <span className="w-12 shrink-0 font-semibold">{line.kind === 'same' ? '' : MARK[line.kind]}</span>
              <span className="min-w-0 break-words whitespace-pre-wrap">{line.text || ' '}</span>
            </div>
          ))}
        </div>
        <SheetFooter className="mt-4 flex-col gap-2 sm:flex-row">
          <Button variant="outline" disabled={busy} onClick={() => onResolve('theirs')}>
            Keep theirs
          </Button>
          <Button variant="outline" disabled={busy} onClick={() => onResolve('both')}>
            Keep both
          </Button>
          <Button disabled={busy} onClick={() => onResolve('mine')}>
            Keep mine
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
