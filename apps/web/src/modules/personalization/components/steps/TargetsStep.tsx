import { Alert, Button, Skeleton } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import type { Targets } from '~/modules/coverage'
import { DEFAULT_PRESETS, TargetsFields, targetsOfPreset, useCoverageSettings } from '~/modules/coverage'

import { useSaveStep } from '../../hooks/useOnboarding'
import { describeStepError } from '../../lib/stepErrors'
import { StepActions } from './StepActions'
import type { StepProps } from './types'

const STANDARD = targetsOfPreset(DEFAULT_PRESETS[1] as (typeof DEFAULT_PRESETS)[number])

function Form({ initial, onDone }: { initial: Targets; onDone: () => void }) {
  const settings = useCoverageSettings().data
  const save = useSaveStep('targets')
  const [targets, setTargets] = useState<Targets>(initial)
  const failure = save.error ? describeStepError(save.error) : null

  function submit(e: FormEvent) {
    e.preventDefault()
    save.mutate(targets, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-8">
      <TargetsFields
        value={targets}
        presets={settings?.target_presets ?? DEFAULT_PRESETS}
        limits={settings?.target_limits ?? { min: 0, max: 10 }}
        onChange={setTargets}
        disabled={save.isPending}
      />
      <p className="text-sm text-muted-foreground">
        These are goals, not rules. Your logged work is always kept, and you can change them later.
      </p>
      <StepActions pending={save.isPending} error={failure?.message} />
    </form>
  )
}

/** Step 4: the three per-chapter targets. A preset is already chosen, so Continue is one tap. */
export function TargetsStep({ onDone }: StepProps) {
  const settings = useCoverageSettings()
  if (settings.isPending) return <Skeleton className="h-72 w-full" aria-busy />
  if (settings.isError) {
    return (
      <Alert variant="error">
        <div className="space-y-2">
          <p>We could not load your plan options.</p>
          <Button size="sm" variant="outline" onClick={() => void settings.refetch()}>
            Try again
          </Button>
        </div>
      </Alert>
    )
  }
  const current = settings.data
  const initial = current?.targets_confirmed ? current.targets : STANDARD
  return <Form initial={initial} onDone={onDone} />
}
