import { Button, ConfidenceDot, confidenceLabel, Lock } from '@artha/design-system'
import { useId } from 'react'

import { confidenceHint } from '../lib/rules'
import type { Confidence } from '../lib/types'

const ORDER: Confidence[] = ['red', 'amber', 'green']

/**
 * Self-rated confidence, shown beside the measured percent (FR-21). Press the selected one again to clear.
 * Locked below 50% chapter coverage: the three options are disabled and the reason is written next to them.
 */
export function ConfidencePicker({
  value,
  onChange,
  disabled,
  coveragePct,
  unlocked,
}: {
  value: Confidence | null
  onChange: (v: Confidence | null) => void
  disabled?: boolean
  coveragePct: number
  /** `confidenceAllowed(coveragePct)`, passed in so the container owns the rule once. */
  unlocked: boolean
}) {
  const hintId = useId()
  return (
    <div className="space-y-3">
      <div role="group" aria-label="How confident do you feel about this chapter?" className="flex flex-wrap gap-2">
        {ORDER.map((c) => (
          <Button
            key={c}
            type="button"
            variant={value === c ? 'secondary' : 'outline'}
            aria-pressed={value === c}
            aria-describedby={unlocked ? undefined : hintId}
            disabled={disabled || !unlocked}
            className={value === c ? 'border border-primary' : ''}
            onClick={() => onChange(value === c ? null : c)}
          >
            <ConfidenceDot value={c} />
            {confidenceLabel(c)}
          </Button>
        ))}
      </div>
      {unlocked ? null : (
        <p id={hintId} className="flex items-start gap-2 text-sm text-muted-foreground">
          <Lock aria-hidden className="mt-0.5 size-4 shrink-0" />
          {confidenceHint(coveragePct)}
        </p>
      )}
    </div>
  )
}
