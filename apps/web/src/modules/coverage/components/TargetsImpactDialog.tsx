import { Button, Dialog, DialogContent, DialogDescription, DialogTitle, LoaderCircle } from '@artha/design-system'

import { impactSentence, targetsLine } from '../lib/targets'
import type { Targets, TargetsImpact } from '../lib/types'

interface Props {
  open: boolean
  impact: TargetsImpact | null
  from: Targets
  to: Targets
  pending: boolean
  onConfirm: () => void
  onCancel: () => void
}

/** Shown before a save that would lower some chapter percentages: what changes, and that nothing is deleted. */
export function TargetsImpactDialog({ open, impact, from, to, pending, onConfirm, onCancel }: Props) {
  return (
    <Dialog open={open} onOpenChange={(next) => (!next && !pending ? onCancel() : undefined)}>
      <DialogContent>
        <DialogTitle>Raise your study targets?</DialogTitle>
        <DialogDescription className="mt-2">
          {impact ? impactSentence(impact.chapters_dropping) : ''} A higher target means more is needed to count a
          chapter as done. Nothing you logged is removed, and you can undo this right after saving.
        </DialogDescription>
        <p className="mt-4 rounded-xl bg-muted p-3 text-sm tabular-nums">
          <span className="text-muted-foreground">Now</span> {targetsLine(from)}
          <span aria-hidden className="mx-2">
            →
          </span>
          <span className="sr-only">to</span>
          <span className="font-semibold">{targetsLine(to)}</span>
          <span className="ml-2 text-muted-foreground">(practice · revisions · mocks)</span>
        </p>
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <Button variant="outline" onClick={onCancel} disabled={pending}>
            Keep current targets
          </Button>
          <Button onClick={onConfirm} disabled={pending}>
            {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
            Save new targets
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
