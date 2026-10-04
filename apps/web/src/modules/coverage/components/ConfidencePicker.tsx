import { Button, ConfidenceDot, confidenceLabel } from '@artha/design-system'

import type { Confidence } from '../lib/types'

const ORDER: Confidence[] = ['red', 'amber', 'green']

/** Self-rated confidence, shown beside the measured percent (FR-21). Press the selected one again to clear. */
export function ConfidencePicker({
  value,
  onChange,
  disabled,
}: {
  value: Confidence | null
  onChange: (v: Confidence | null) => void
  disabled?: boolean
}) {
  return (
    <div role="group" aria-label="How confident do you feel about this chapter?" className="flex flex-wrap gap-2">
      {ORDER.map((c) => (
        <Button
          key={c}
          type="button"
          variant={value === c ? 'secondary' : 'outline'}
          aria-pressed={value === c}
          disabled={disabled}
          className={value === c ? 'border border-primary' : ''}
          onClick={() => onChange(value === c ? null : c)}
        >
          <ConfidenceDot value={c} />
          {confidenceLabel(c)}
        </Button>
      ))}
    </div>
  )
}
