import { Alert, Card } from '@artha/design-system'

import type { ElectiveSlot } from '../lib/types'
import { ElectiveChoice } from './ElectiveChoice'

interface Props {
  slots: ElectiveSlot[]
  pending: boolean
  error?: string
  onChange: (slotKey: string, subjectId: string | null) => void
}

/** On the syllabus map: change the elective for each optional paper. Only the chosen one counts toward coverage. */
export function ElectivePicker({ slots, pending, error, onChange }: Props) {
  const undecided = slots.filter((s) => !s.chosen).length
  return (
    <Card className="space-y-6 p-6" id="electives">
      <div className="space-y-1">
        <h2 className="font-display text-xl font-bold">Your elective papers</h2>
        <p className="text-sm text-muted-foreground">
          You sit one option for each elective paper. Only your choice counts toward your coverage. Your progress in the
          others is kept if you change your mind.
        </p>
      </div>
      {undecided > 0 ? (
        <Alert variant="info">
          {undecided === 1 ? 'One elective paper is' : `${undecided} elective papers are`} not chosen yet, so
          {undecided === 1 ? ' it is' : ' they are'} left out of your percentages.
        </Alert>
      ) : null}
      {slots.map((slot) => (
        <ElectiveChoice
          key={slot.key}
          slot={slot}
          value={slot.chosen}
          disabled={pending}
          onChange={(id) => onChange(slot.key, id)}
        />
      ))}
      {error ? <Alert variant="error">{error}</Alert> : null}
    </Card>
  )
}
