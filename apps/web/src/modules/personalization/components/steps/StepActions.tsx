import { Alert, Button, LoaderCircle } from '@artha/design-system'

interface Props {
  pending: boolean
  /** One sentence for the whole step when saving failed. */
  error?: string
  continueLabel?: string
  continueDisabled?: boolean
  /** Optional steps: a quiet "Skip for now". */
  onSkip?: () => void
  skipPending?: boolean
}

/** The bottom of every step: the error, Continue (a submit button), and Skip when the step is optional. */
export function StepActions({
  pending,
  error,
  continueLabel = 'Continue',
  continueDisabled,
  onSkip,
  skipPending,
}: Props) {
  return (
    <div className="space-y-4">
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="lg" disabled={pending || skipPending || continueDisabled}>
          {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
          {continueLabel}
        </Button>
        {onSkip ? (
          <Button type="button" variant="ghost" size="lg" onClick={onSkip} disabled={pending || skipPending}>
            {skipPending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
            Skip for now
          </Button>
        ) : null}
      </div>
    </div>
  )
}
