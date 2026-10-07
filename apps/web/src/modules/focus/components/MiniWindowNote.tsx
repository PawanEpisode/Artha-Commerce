import { Button, Info } from '@artha/design-system'

/**
 * The honest one-line note at the first open of the fallback window: it does not stay on top, and when something
 * covers it a round end follows the usual away rules. Presentational; the container decides when it shows.
 */
export function MiniWindowNote({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div role="note" className="flex items-start gap-2 border-b border-border bg-secondary px-3 py-2 text-sm">
      <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-primary" />
      <p className="min-w-0 flex-1">
        This window does not stay on top in this browser. If it is hidden behind others, a round end follows the usual
        away rules.
      </p>
      <Button size="sm" variant="outline" onClick={onDismiss} className="min-h-10 shrink-0">
        Got it
      </Button>
    </div>
  )
}
