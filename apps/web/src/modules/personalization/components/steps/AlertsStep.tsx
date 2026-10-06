import { AlertsStepContainer } from '~/modules/notifications'

import { useSaveStep, useSkipStep } from '../../hooks/useOnboarding'
import type { StepProps } from './types'

/**
 * Step 8 (optional): push alerts. The notifications module owns the whole screen and the consent record; this only
 * saves the onboarding step once a decision exists (the API checks) and moves the flow on.
 */
export function AlertsStep({ onDone }: StepProps) {
  const save = useSaveStep('alerts')
  const skip = useSkipStep('alerts')
  return (
    <AlertsStepContainer
      onFinish={async () => {
        await save.mutateAsync({})
        onDone()
      }}
      onSkip={async () => {
        await skip.mutateAsync()
        onDone()
      }}
    />
  )
}
