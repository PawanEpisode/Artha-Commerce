import { TextField } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { useSaveStep } from '../../hooks/useOnboarding'
import { checkName, NAME_MAX } from '../../lib/names'
import { describeStepError } from '../../lib/stepErrors'
import { StepActions } from './StepActions'
import type { StepProps } from './types'

/** Step 1: the name, prefilled from the provider or the email (never stored until confirmed here). */
export function ProfileStep({ bootstrap, onDone }: StepProps) {
  const save = useSaveStep('profile')
  const [name, setName] = useState(bootstrap.full_name || bootstrap.name_suggestion)
  const [touched, setTouched] = useState(false)
  const checked = checkName(name)
  const failure = save.error ? describeStepError(save.error) : null
  const fieldError = touched && !checked.ok ? checked.message : failure?.fields.full_name

  function submit(e: FormEvent) {
    e.preventDefault()
    setTouched(true)
    if (!checked.ok) return
    save.mutate({ full_name: checked.name }, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-8">
      <TextField
        label="Your name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onBlur={() => setTouched(true)}
        autoComplete="name"
        maxLength={NAME_MAX + 20}
        error={fieldError}
        hint="You can change it later in Account."
      />
      <StepActions pending={save.isPending} error={fieldError ? undefined : failure?.message} />
    </form>
  )
}
