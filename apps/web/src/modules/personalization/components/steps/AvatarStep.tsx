import { Button } from '@artha/design-system'

import { useBootstrap } from '../../hooks/useBootstrap'
import { useSkipStep } from '../../hooks/useOnboarding'
import { describeStepError } from '../../lib/stepErrors'
import { AvatarEditor } from '../AvatarEditor'
import { IdentityAvatar } from '../IdentityAvatar'
import { StepActions } from './StepActions'
import type { StepProps } from './types'

/** Step 7 (optional): a photo or one of the avatars. Picking either already satisfies the step; Continue just moves on. */
export function AvatarStep({ bootstrap, onDone }: StepProps) {
  // Read the live avatar: the editor updates it in place when a photo or avatar is chosen.
  const live = useBootstrap().data ?? bootstrap
  const skip = useSkipStep('avatar')
  const chosen = live.avatar.kind !== 'initials'
  const failure = skip.error ? describeStepError(skip.error) : null

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-5">
        <IdentityAvatar size={96} />
        <p className="text-muted-foreground">
          {chosen
            ? 'Looking good. You can change it any time in Account.'
            : 'Until you choose one, your initials show.'}
        </p>
      </div>
      <AvatarEditor avatar={live.avatar} />
      {chosen ? (
        <div className="flex flex-wrap gap-3">
          <Button size="lg" onClick={onDone}>
            Continue
          </Button>
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            skip.mutate(undefined, { onSuccess: onDone })
          }}
        >
          <StepActions
            pending={false}
            skipPending={skip.isPending}
            error={failure?.message}
            continueLabel="Continue with initials"
          />
        </form>
      )}
    </div>
  )
}
