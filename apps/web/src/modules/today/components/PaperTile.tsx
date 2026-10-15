import { ProgressBar } from '@artha/design-system'

import type { TileView } from '../lib/plan'

/** A paper's share of today as a filter button: "2 of 3 done". Pressed = the list below shows only this paper. */
export function PaperTile({ tile, pressed, onSelect }: { tile: TileView; pressed: boolean; onSelect: () => void }) {
  const percent = tile.total ? Math.round((tile.done / tile.total) * 100) : 0
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onSelect}
      className={`flex min-h-11 w-full min-w-0 flex-col gap-2 rounded-xl border p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
        pressed ? 'border-primary bg-secondary' : 'border-border bg-card hover:bg-muted'
      }`}
    >
      <span className="text-sm font-semibold break-words">{tile.name}</span>
      <ProgressBar value={percent} size="sm" label={`${tile.name} progress`} />
      <span className="text-xs text-muted-foreground">
        {tile.done} of {tile.total} done
      </span>
    </button>
  )
}
