import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { FollowUpCard } from '../components/FollowUpCard'
import { useNotificationSettings } from '../hooks/useNotificationQueries'
import { usePushCapability } from '../hooks/usePushCapability'
import { usePushEnable } from '../hooks/usePushEnable'
import { enableAnnouncement } from '../lib/alertsStep'
import { postPermissionState } from '../lib/api'
import { shouldAskFollowUp } from '../lib/followUp'
import { notificationKeys } from '../lib/keys'

type Stage = 'hidden' | 'ask' | 'done'

/**
 * The follow-up ask (W2.5b). Mount it on the focus page and pass how many rounds ended during this visit. It shows once
 * the server says an ask is due and a round has just finished, counts the ask as soon as it is shown (the server
 * ignores a repeat and enforces the 14 day spacing and the cap), and stays until the student answers, so a refetch that
 * flips `followup_due` off does not make it vanish under their hands.
 */
export function FollowUpAskContainer({ roundsFinished }: { roundsFinished: number }) {
  const qc = useQueryClient()
  const flagOn = useFeatureFlag('notifications_ui')
  const settings = useNotificationSettings()
  const capability = usePushCapability()
  const { enable, busy } = usePushEnable('followup')
  const [stage, setStage] = useState<Stage>('hidden')
  const [message, setMessage] = useState('')
  const heading = useRef<HTMLHeadingElement>(null)
  const asked = useRef(false)

  const eligible = shouldAskFollowUp({
    flagOn,
    due: settings.data?.followup_due === true,
    view: capability.view,
    roundsFinished,
  })

  useEffect(() => {
    if (!eligible || asked.current) return
    asked.current = true
    setStage('ask')
    // Best effort: a failed record only means the ask is not counted, never that the student is blocked.
    void postPermissionState('pre_prompt_shown', 'followup')
      .then(() => qc.invalidateQueries({ queryKey: notificationKeys.settings }))
      .catch(() => undefined)
  }, [eligible, qc])

  // The buttons that had focus disappear when the card changes: move focus to its heading.
  useEffect(() => {
    if (stage === 'done') heading.current?.focus()
  }, [stage])

  async function onEnable() {
    if (!capability.environment) return
    const outcome = await enable(capability.environment)
    await capability.refresh()
    await Promise.all([
      qc.invalidateQueries({ queryKey: notificationKeys.devices }),
      qc.invalidateQueries({ queryKey: notificationKeys.settings }),
    ])
    setMessage(enableAnnouncement(outcome.status))
    setStage('done')
  }

  async function onNotNow() {
    setStage('hidden')
    try {
      await postPermissionState('dismissed', 'followup')
      await qc.invalidateQueries({ queryKey: notificationKeys.settings })
    } catch {
      // Not recorded: the server still counted the ask, so the spacing rule holds.
    }
  }

  if (stage === 'hidden') return null
  return (
    <FollowUpCard
      stage={stage}
      message={message}
      enabling={busy}
      headingRef={heading}
      onEnable={() => void onEnable()}
      onNotNow={() => void onNotNow()}
      onClose={() => setStage('hidden')}
    />
  )
}
