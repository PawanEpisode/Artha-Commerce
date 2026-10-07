import { useEffect, useState } from 'react'

import { track, useFeatureFlag } from '~/modules/observability'

import { PopOutPromptCard } from '../components/PopOutPromptCard'
import { useSaveFocusSettings } from '../hooks/useFocusSettings'
import { useDesktopBrowser, useDocumentPipSupported } from '../hooks/usePipSupport'
import { usePopOut } from '../hooks/usePopOut'
import { promptEligible } from '../lib/popout'
import type { FocusSettings, Phase } from '../lib/types'

type Stage = 'waiting' | 'shown' | 'answered'

/**
 * The start-of-round prompt (X-01 W4.3, decision D11): offered once ever per student, on a desktop browser with
 * Document Picture-in-Picture, while a focus round runs. It counts as seen the moment it shows (`popout_prompt_seen`,
 * written once), so a reload never brings it back whatever the student did. It stays up until they answer, the round
 * ends or a window opens, even after the saved flag turns the eligibility off under it. The Pop out click is the one
 * that opens the window, so it asks the browser first and only then does anything else.
 */
export function PopOutPromptContainer({
  phase,
  settings,
}: {
  phase: Phase | null
  settings: FocusSettings | undefined
}) {
  const pop = usePopOut()
  const supported = useDocumentPipSupported()
  const desktop = useDesktopBrowser()
  const flagOn = useFeatureFlag('floating_timer')
  const { mutate } = useSaveFocusSettings()
  const [stage, setStage] = useState<Stage>('waiting')
  const [always, setAlways] = useState(false)

  const where = {
    supported,
    desktop,
    flagOn,
    popoutOnStart: settings?.popout_on_start ?? true,
    phase,
    popoutOpen: pop.isOpen,
  }
  // Until the settings are known the prompt is treated as seen, so it never flashes up and then disappears.
  const eligible = promptEligible({ ...where, popoutPromptSeen: settings?.popout_prompt_seen ?? true })
  const stillFits = stage === 'shown' && promptEligible({ ...where, popoutPromptSeen: false })

  useEffect(() => {
    if (stage === 'waiting' && eligible) {
      setStage('shown')
      track('popout_prompt_shown', {})
      mutate({ popout_prompt_seen: true })
    } else if (stage === 'shown' && !stillFits) setStage('answered')
  }, [stage, eligible, stillFits, mutate])

  if (!stillFits || !settings) return null

  const popOut = () => {
    // First, before anything else: the browser only opens the window while this click is fresh.
    const opening = pop.open(settings.popout_size, { source: 'prompt', timer: 'focus' })
    track('popout_prompt_answered', { answer: 'popped_out', always })
    setStage('answered')
    void opening.then((opened) => {
      if (opened && always) mutate({ popout_on_start: true })
    })
  }
  const notNow = () => {
    track('popout_prompt_answered', { answer: 'not_now', always: false })
    setStage('answered')
  }
  return <PopOutPromptCard always={always} onAlwaysChange={setAlways} onPopOut={popOut} onNotNow={notNow} />
}
