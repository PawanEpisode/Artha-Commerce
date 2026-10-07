import { useEffect, useRef, useState } from 'react'

import { DigestOfferCard } from '../components/DigestOfferCard'
import { DigestStatusCard } from '../components/DigestStatusCard'
import { useDigest } from '../hooks/useDigest'
import { notificationAnalytics } from '../lib/analytics'
import { digestCard, digestDoneMessage } from '../lib/digest'
import { notify } from '../lib/notify'

type Place = 'settings' | 'inbox'
type Answer = 'accept' | 'decline' | 'stop'

/**
 * The daily digest offer and switch (W3.7, FR-N34), on the inbox and on the notifications settings page. The offer
 * counts as made as soon as it is shown (the server then waits 30 days before offering again), so a reload does not
 * bring it back, and it stays on screen until the student answers it. After an answer, focus moves to the card that
 * says what happened, so it is never lost with the button that was pressed.
 */
export function DigestContainer({ place }: { place: Place }) {
  const { flagOn, query, answer } = useDigest()
  const { mutate, mutateAsync, isPending } = answer
  const [shown, setShown] = useState(false)
  const [answered, setAnswered] = useState<Answer | null>(null)
  const [closed, setClosed] = useState(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const state = query.data
  const pinned = shown && answered === null && !state?.enabled
  const card = pinned ? 'offer' : digestCard(state, place, flagOn)
  // In settings an accepted digest shows its own card; every other answer is said in place until it is closed.
  const done = answered !== null && !closed && !(answered === 'accept' && place === 'settings')

  useEffect(() => {
    if (card !== 'offer' || shown) return
    setShown(true)
    notificationAnalytics.digestOfferShown(place)
    void mutateAsync('seen').catch(() => undefined) // best effort: the card is shown either way
  }, [card, shown, place, mutateAsync])

  useEffect(() => {
    if (answered !== null) heading.current?.focus()
  }, [answered])

  const respond = (choice: Answer) =>
    mutate(choice, {
      onSuccess: () => {
        notificationAnalytics.digestAnswered(choice, place)
        setClosed(false)
        setAnswered(choice)
      },
      onError: (error) => notify.error(error, 'Could not save that choice.'),
    })

  if (!state) return null
  if (done && answered) {
    return (
      <DigestOfferCard
        stage="done"
        time={state.time}
        message={digestDoneMessage(answered, state.time)}
        busy={false}
        headingRef={heading}
        onAccept={() => undefined}
        onDecline={() => undefined}
        onClose={() => setClosed(true)}
      />
    )
  }
  if (card === 'status') {
    return <DigestStatusCard time={state.time} busy={isPending} headingRef={heading} onStop={() => respond('stop')} />
  }
  if (card !== 'offer') return null
  return (
    <DigestOfferCard
      stage="offer"
      time={state.time}
      message=""
      busy={isPending}
      onAccept={() => respond('accept')}
      onDecline={() => respond('decline')}
      onClose={() => undefined}
    />
  )
}
