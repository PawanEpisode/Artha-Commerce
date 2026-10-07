import {
  Alert,
  Badge,
  Button,
  SegmentedControl,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
} from '@artha/design-system'

import { RichText } from '~/lib/richtext'

import { diffLines, hasChanges } from '../lib/conflict'
import { formatDate, formatTime, pluralize } from '../lib/format'
import type { VersionDetail, VersionRow } from '../lib/types'

export type VersionMode = 'view' | 'compare'

const SOURCE: Record<VersionRow['source'], string> = {
  autosave: 'Autosaved',
  manual: 'Saved',
  restore: 'Restored',
  merge: 'Merged',
  ai: 'Written by AI',
}

interface VersionPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  versions: readonly VersionRow[] | undefined
  isPending: boolean
  isError: boolean
  onRetry: () => void
  currentRev: number
  currentBody: string
  selectedRev: number | undefined
  onSelect: (rev: number | undefined) => void
  detail: VersionDetail | undefined
  detailPending: boolean
  mode: VersionMode
  onMode: (mode: VersionMode) => void
  onRestore: (version: VersionRow) => void
  restoring: boolean
  /** Restoring writes a new version, so it needs a connection. */
  online: boolean
  resolveImage?: (attachmentId: string) => string | undefined
}

/** The history of one note: a list of versions, then the chosen one to read, compare with the current text, or restore. */
export function VersionPanel(props: VersionPanelProps) {
  const { versions, selectedRev, detail } = props
  const selected = versions?.find((v) => v.rev === selectedRev)
  return (
    <Sheet open={props.open} onOpenChange={props.onOpenChange}>
      <SheetContent side="right" className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Version history</SheetTitle>
          <SheetDescription>
            Every saved version of this note. Restoring one adds it as the newest, so nothing is lost.
          </SheetDescription>
        </SheetHeader>
        {props.isPending ? (
          <div aria-busy="true" className="space-y-2">
            <span role="status" className="sr-only">
              Loading versions…
            </span>
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : props.isError || !versions ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              <span>We could not load the history.</span>
              <Button size="sm" variant="outline" onClick={props.onRetry}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : selected ? (
          <div className="space-y-4">
            <Button variant="ghost" size="sm" onClick={() => props.onSelect(undefined)}>
              Back to all versions
            </Button>
            <h3 className="font-display text-lg font-bold">
              Version {selected.rev}
              {selected.rev === props.currentRev ? <Badge className="ml-2">Current</Badge> : null}
            </h3>
            <p className="text-sm text-muted-foreground">
              {SOURCE[selected.source]} on {formatDate(selected.created_at)} at {formatTime(selected.created_at)}
            </p>
            <SegmentedControl
              label="How to read this version"
              value={props.mode}
              onValueChange={props.onMode}
              options={[
                { value: 'view', label: 'Read' },
                { value: 'compare', label: 'Compare' },
              ]}
            />
            {props.detailPending || !detail ? (
              <Skeleton className="h-40 w-full" />
            ) : props.mode === 'view' ? (
              <RichText markdown={detail.body_md} resolveImage={props.resolveImage} />
            ) : (
              <Comparison older={detail.body_md} current={props.currentBody} />
            )}
            <Button
              disabled={!props.online || props.restoring || selected.rev === props.currentRev}
              onClick={() => props.onRestore(selected)}
            >
              {props.restoring ? 'Restoring…' : `Restore version ${selected.rev}`}
            </Button>
            {!props.online ? <p className="text-sm text-muted-foreground">Restoring needs a connection.</p> : null}
          </div>
        ) : versions.length === 0 ? (
          <p className="text-muted-foreground">No earlier versions yet. They appear as you edit.</p>
        ) : (
          <ul aria-label="Versions" className="space-y-2">
            {versions.map((v) => (
              <li key={v.rev}>
                <button
                  type="button"
                  onClick={() => props.onSelect(v.rev)}
                  className="flex min-h-14 w-full flex-col items-start rounded-xl border bg-card px-4 py-2 text-left outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40"
                >
                  <span className="font-semibold">
                    Version {v.rev}
                    {v.rev === props.currentRev ? ' (current)' : ''}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {SOURCE[v.source]}, {formatDate(v.created_at)} {formatTime(v.created_at)},{' '}
                    {pluralize(v.chars, 'character')}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </SheetContent>
    </Sheet>
  )
}

function Comparison({ older, current }: { older: string; current: string }) {
  const lines = diffLines(older, current)
  if (!hasChanges(lines))
    return <p className="text-muted-foreground">This version has the same text as the current one.</p>
  return (
    <div
      role="region"
      aria-label="Differences from the current text"
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scrollable region must be reachable by keyboard
      tabIndex={0}
      className="max-h-80 overflow-auto rounded-lg border bg-card p-2 font-mono text-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
    >
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
          <span className="w-16 shrink-0 font-semibold">
            {line.kind === 'same' ? '' : line.kind === 'mine' ? 'Now only' : 'Then only'}
          </span>
          <span className="min-w-0 break-words whitespace-pre-wrap">{line.text || ' '}</span>
        </div>
      ))}
    </div>
  )
}
