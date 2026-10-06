import { useState } from 'react'

import { useAuth } from '~/modules/auth'
import { stepCopy, useOnboardingState } from '~/modules/personalization'

import { SetupCards } from '../components/SetupCards'
import { notify } from '../lib/notify'
import { dismiss, readDismissed, setupCardFor, skippedSteps } from '../lib/setupCards'

/** "Finish your setup": one card per optional step the student skipped. Absent when there is nothing to finish. */
export function SetupWidget() {
  const { user } = useAuth()
  const state = useOnboardingState()
  const [dismissed, setDismissed] = useState<string[]>(() => (user ? readDismissed(user.id) : []))
  if (!state.data || !user) return null

  const cards = skippedSteps(state.data, dismissed).map((key) => ({ key, ...setupCardFor(key, stepCopy(key).title) }))
  if (cards.length === 0) return null

  return (
    <section aria-labelledby="widget-setup" className="space-y-3 lg:col-span-2">
      <h2 id="widget-setup" className="text-base font-bold">
        Finish your setup
      </h2>
      <SetupCards
        cards={cards}
        onDismiss={(key) => {
          setDismissed(dismiss(user.id, key))
          notify.setupCardHidden()
        }}
      />
    </section>
  )
}
