import { Checkbox, DurationField, Label } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { useSaveStep } from '../../hooks/useOnboarding'
import { describeStepError } from '../../lib/stepErrors'
import { StepActions } from './StepActions'
import type { StepProps } from './types'

export const DEFAULT_DAILY_MINUTES = 180
export const MIN_DAILY_MINUTES = 15
export const MAX_DAILY_MINUTES = 960

/** Step 3: study time per day (default 3 h) and whether it is also the tracker's daily goal. */
export function HoursStep({ bootstrap, onDone }: StepProps) {
  const save = useSaveStep('hours')
  const [minutes, setMinutes] = useState<number | null>(bootstrap.course?.daily_minutes ?? DEFAULT_DAILY_MINUTES)
  const [asGoal, setAsGoal] = useState(true)
  const failure = save.error ? describeStepError(save.error) : null
  const invalid = minutes === null || minutes < MIN_DAILY_MINUTES || minutes > MAX_DAILY_MINUTES

  function submit(e: FormEvent) {
    e.preventDefault()
    if (invalid || minutes === null) return
    save.mutate({ daily_minutes: minutes, use_as_goal: asGoal }, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-8">
      <DurationField
        label="Study time per day"
        valueMinutes={minutes}
        onChangeMinutes={setMinutes}
        maxMinutes={MAX_DAILY_MINUTES}
        stepMinutes={15}
        hint="Between 15 minutes and 16 hours."
        error={
          invalid && minutes !== null
            ? 'Enter between 15 minutes and 16 hours.'
            : minutes === null
              ? 'Enter your daily study time.'
              : undefined
        }
      />
      <div className="flex items-start gap-3">
        <Checkbox id="use-as-goal" checked={asGoal} onCheckedChange={(v) => setAsGoal(v === true)} />
        <div>
          <Label htmlFor="use-as-goal" className="text-base">
            Use this as my daily goal
          </Label>
          <p className="text-sm text-muted-foreground">
            The time tracker will show your progress against it. An existing goal is never replaced.
          </p>
        </div>
      </div>
      <StepActions pending={save.isPending} error={failure?.message} continueDisabled={invalid} />
    </form>
  )
}
