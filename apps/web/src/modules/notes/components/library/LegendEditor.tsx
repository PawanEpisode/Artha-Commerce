import { Button, TextField } from '@artha/design-system'
import { useState } from 'react'

import { LEGEND_NAME_MAX, legendChanged, tidyLegend, validateLegend } from '../../lib/legend-edit'
import { COLOR_KEYS, type ColorLegend } from '../../lib/library-types'
import { ColorDot } from './HighlightRow'

interface LegendEditorProps {
  legend: ColorLegend
  saving?: boolean
  /** Tidied names that passed validation. */
  onSave: (legend: ColorLegend) => void
}

/** Five names for the five highlight colours: 1 to 24 characters, each different. Saved together, so the set is never half renamed. */
export function LegendEditor({ legend, saving, onSave }: LegendEditorProps) {
  const [draft, setDraft] = useState(legend)
  const [shown, setShown] = useState(false)
  const errors = validateLegend(draft)
  const invalid = Object.keys(errors).length > 0
  const changed = legendChanged(draft, legend)
  return (
    <form
      aria-label="Colour names"
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault()
        setShown(true)
        if (!invalid) onSave(tidyLegend(draft))
      }}
    >
      <p className="text-sm text-muted-foreground">
        Name what each colour means to you, like &ldquo;Formula&rdquo; or &ldquo;Doubt&rdquo;. Highlights show these
        names instead of colours.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {COLOR_KEYS.map((key) => (
          <div key={key} className="flex items-start gap-2">
            <span className="mt-9 grid size-5 shrink-0 place-items-center">
              <ColorDot color={key} />
            </span>
            <TextField
              className="min-w-0 flex-1"
              label={`Name for colour ${COLOR_KEYS.indexOf(key) + 1}`}
              value={draft[key]}
              maxLength={LEGEND_NAME_MAX + 8}
              error={shown ? errors[key] : undefined}
              onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
            />
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!changed || saving} loading={saving}>
          Save names
        </Button>
        {changed ? (
          <Button type="button" variant="ghost" onClick={() => setDraft(legend)}>
            Undo changes
          </Button>
        ) : null}
      </div>
    </form>
  )
}
