import { useEffect, useRef, useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { InstallOfferCard } from '../components/InstallOfferCard'
import { useInstallPrompt } from '../hooks/useInstallPrompt'
import { notificationAnalytics } from '../lib/analytics'
import { readEnvironment } from '../lib/browser'
import { type InstallKind, installKind, installOfferDue } from '../lib/install'
import { addDeviceRounds, deviceRounds, lastOfferedAt, markOffered } from '../lib/installMemory'
import type { Environment } from '../lib/platform'

type Stage = 'waiting' | 'shown' | 'closed'

/**
 * The install offer (X-01 W4.5, FR-C7). Mount it on the focus page and pass how many rounds ended during this visit.
 * It counts finished rounds on this device, and shows after the second one, at most once every 30 days, never in the
 * installed app or another app's browser. Like the other one-time offers it counts as shown the moment it appears, and
 * stays until the student answers. With the `floating_timer` flag off it never shows.
 */
export function InstallOfferContainer({ roundsFinished }: { roundsFinished: number }) {
  const flagOn = useFeatureFlag('floating_timer')
  const { canPrompt, prompt } = useInstallPrompt()
  // Read on the client only: the server has no idea what browser this is.
  const [env, setEnv] = useState<Environment | null>(null)
  useEffect(() => setEnv(readEnvironment()), [])

  // Every round that ends on this page counts toward this device, once.
  const counted = useRef(0)
  const [rounds, setRounds] = useState<number | null>(null)
  useEffect(() => {
    if (roundsFinished > counted.current) {
      setRounds(addDeviceRounds(roundsFinished - counted.current))
      counted.current = roundsFinished
    } else setRounds((current) => current ?? deviceRounds())
  }, [roundsFinished])

  const [stage, setStage] = useState<Stage>('waiting')
  const [shownKind, setShownKind] = useState<InstallKind | null>(null)
  const [busy, setBusy] = useState(false)

  const kind = env ? installKind(env, canPrompt) : null
  const due = installOfferDue({
    flagOn,
    kind,
    deviceRounds: rounds ?? 0,
    roundsFinished,
    lastOfferedAt: lastOfferedAt(),
    now: Date.now(),
  })

  useEffect(() => {
    if (stage !== 'waiting' || !due || !kind || !env) return
    setStage('shown')
    setShownKind(kind)
    markOffered(Date.now())
    if (kind !== 'prompt') notificationAnalytics.pwaInstallResult('guide_shown', kind, env)
  }, [stage, due, kind, env])

  // The card stays until answered, but not past the flag going off or the browser stopping to offer an install.
  const stillOffered = flagOn && env !== null && (shownKind !== 'prompt' || canPrompt || busy)
  if (stage !== 'shown' || !shownKind || !stillOffered) return null

  const install = async () => {
    if (!env) return
    setBusy(true)
    const result = await prompt()
    setBusy(false)
    if (result !== 'unavailable') notificationAnalytics.pwaInstallResult(result, shownKind, env)
    setStage('closed')
  }
  return (
    <InstallOfferCard
      kind={shownKind}
      busy={busy}
      onInstall={() => void install()}
      onClose={() => setStage('closed')}
    />
  )
}
