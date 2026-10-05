import { RadioCardItem, RadioGroup } from '@artha/design-system'

import type { ElectiveSlotInfo } from '~/modules/syllabus'

const LATER = 'later'

interface Props {
  slot: ElectiveSlotInfo
  /** Chosen subject id, or null/'' while undecided. */
  value: string | null
  disabled?: boolean
  onChange: (subjectId: string | null) => void
}

/** One elective paper: pick one of its options, or decide later. Shared by onboarding and the syllabus map. */
export function ElectiveChoice({ slot, value, disabled, onChange }: Props) {
  return (
    <fieldset className="space-y-3" disabled={disabled}>
      <legend className="mb-2 font-display text-lg font-bold">
        {slot.name}
        <span className="ml-2 text-sm font-normal text-muted-foreground">choose one</span>
      </legend>
      <RadioGroup
        value={value ?? LATER}
        onValueChange={(v) => onChange(v === LATER ? null : v)}
        aria-label={slot.name}
        className="sm:grid-cols-1"
      >
        {slot.options.map((o) => (
          <RadioCardItem key={o.id} value={o.id}>
            <span className="block font-semibold">{o.name}</span>
          </RadioCardItem>
        ))}
        <RadioCardItem value={LATER}>
          <span className="block font-semibold">I will decide later</span>
          <span className="text-sm text-muted-foreground">
            This paper stays out of your percentages until you choose.
          </span>
        </RadioCardItem>
      </RadioGroup>
    </fieldset>
  )
}
