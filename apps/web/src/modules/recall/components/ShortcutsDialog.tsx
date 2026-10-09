import { Dialog, DialogContent, DialogDescription, DialogTitle, Kbd } from '@artha/design-system'

export const SHORTCUTS: ReadonlyArray<{ keys: string[]; does: string }> = [
  { keys: ['Space', 'Enter'], does: 'Show the answer' },
  { keys: ['1'], does: 'Again: I did not remember it' },
  { keys: ['2'], does: 'Hard: I remembered it with effort' },
  { keys: ['3'], does: 'Good: I remembered it' },
  { keys: ['4'], does: 'Easy: it came straight away' },
  { keys: ['U'], does: 'Undo the last answer' },
  { keys: ['S'], does: 'Suspend this card' },
  { keys: ['B'], does: 'Bury this card until tomorrow' },
  { keys: ['E'], does: 'Edit this card' },
  { keys: ['?'], does: 'Show this list' },
]

export function ShortcutsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Keyboard shortcuts</DialogTitle>
        <DialogDescription>On a phone, swipe left for Again and right for Good, or use the buttons.</DialogDescription>
        <dl className="mt-4 grid gap-2">
          {SHORTCUTS.map((s) => (
            <div key={s.does} className="flex items-center justify-between gap-4 text-sm">
              <dt className="flex gap-1">
                {s.keys.map((k) => (
                  <Kbd key={k}>{k}</Kbd>
                ))}
              </dt>
              <dd className="text-right text-muted-foreground">{s.does}</dd>
            </div>
          ))}
        </dl>
      </DialogContent>
    </Dialog>
  )
}
