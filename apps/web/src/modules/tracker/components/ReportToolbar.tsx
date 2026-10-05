import { Download, SegmentedControl, TextField } from '@artha/design-system'
import { Button } from '@artha/design-system'

import { type DateRange, PRESET_LABELS, RANGE_PRESETS, type RangePreset } from '../lib/range'

interface Props {
  preset: RangePreset
  range: DateRange
  onPreset: (preset: RangePreset) => void
  onCustom: (range: DateRange) => void
  problem: string | null
  onExport: () => void
  exporting: boolean
}

/** The range controls shared by every report. The range lives in the URL, so a refresh or a link keeps it. */
export function ReportToolbar({ preset, range, onPreset, onCustom, problem, onExport, exporting }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedControl<RangePreset>
          label="Date range"
          value={preset}
          onValueChange={onPreset}
          options={RANGE_PRESETS.map((p) => ({ value: p, label: PRESET_LABELS[p] }))}
        />
        <Button variant="outline" size="sm" onClick={onExport} disabled={exporting}>
          <Download aria-hidden /> Download CSV
        </Button>
      </div>
      {preset === 'custom' ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField
            label="From"
            type="date"
            value={range.from}
            max={range.to}
            onChange={(e) => onCustom({ ...range, from: e.target.value })}
          />
          <TextField
            label="To"
            type="date"
            value={range.to}
            min={range.from}
            error={problem ?? undefined}
            onChange={(e) => onCustom({ ...range, to: e.target.value })}
          />
        </div>
      ) : null}
    </div>
  )
}
