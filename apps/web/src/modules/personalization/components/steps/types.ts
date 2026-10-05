import type { Bootstrap } from '../../lib/types'

/** What every onboarding step screen receives. Saving goes through the step's own hook; navigation is the flow's job. */
export interface StepProps {
  bootstrap: Bootstrap
  /** Called after the step is saved (or, for an optional step, skipped). */
  onDone: () => void
}
