import { Button, Dialog, DialogContent, DialogDescription, DialogTitle, Label } from '@artha/design-system'
import { useState } from 'react'

import { type Merge, resolve } from '../lib/cardConflict'
import { FIELD_TEXT } from '../lib/cardKinds'

type Choice = Record<string, 'mine' | 'theirs'>

/**
 * The card changed somewhere else while she was editing. Fields only one side touched are already merged; for each field
 * both sides changed she picks one. Nothing is lost: the other version stays on screen until she chooses.
 */
export function ConflictDialog({
  merge,
  busy,
  onResolve,
  onCancel,
}: {
  merge: Merge
  busy?: boolean
  onResolve: (fields: Record<string, string>) => void
  onCancel: () => void
}) {
  const [choice, setChoice] = useState<Choice>({})
  const done = merge.conflicts.every((c) => choice[c.field] !== undefined)
  return (
    <Dialog open onOpenChange={(open) => (!open ? onCancel() : undefined)}>
      <DialogContent className="max-h-[90dvh] max-w-2xl overflow-y-auto">
        <DialogTitle>This card was changed somewhere else</DialogTitle>
        <DialogDescription>
          Another device or tab saved a different version. Pick which one to keep for each part below. The rest has been
          merged for you.
        </DialogDescription>
        <div className="space-y-5">
          {merge.conflicts.map((c) => {
            const label = FIELD_TEXT[c.field]?.label ?? c.field
            return (
              <fieldset key={c.field} className="space-y-2">
                <legend className="text-sm font-semibold">{label}</legend>
                {(['mine', 'theirs'] as const).map((side) => {
                  const id = `${c.field}-${side}`
                  return (
                    <div key={side} className="flex items-start gap-3 rounded-lg border border-border p-3">
                      <input
                        id={id}
                        type="radio"
                        name={`conflict-${c.field}`}
                        className="mt-1 size-4"
                        checked={choice[c.field] === side}
                        onChange={() => setChoice((x) => ({ ...x, [c.field]: side }))}
                      />
                      <Label htmlFor={id} className="grid flex-1 gap-1 font-normal">
                        <span className="text-sm font-medium">
                          {side === 'mine' ? 'Your version' : 'The other version'}
                        </span>
                        <span className="text-sm break-words whitespace-pre-wrap text-muted-foreground">
                          {(side === 'mine' ? c.mine : c.theirs) || '(empty)'}
                        </span>
                      </Label>
                    </div>
                  )
                })}
              </fieldset>
            )
          })}
        </div>
        <div className="flex flex-wrap justify-end gap-3">
          <Button variant="outline" onClick={onCancel}>
            Keep editing
          </Button>
          <Button disabled={!done || busy} onClick={() => onResolve(resolve(merge, choice))}>
            Save this version
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
