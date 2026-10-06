import { useMutation } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import { notificationAnalytics } from '../lib/analytics'
import { sendTestPush } from '../lib/api'
import type { NotificationDevice } from '../lib/schemas'
import { pickTestDevice, statusFromError, type TestStatus } from '../lib/testPush'

/**
 * "Send me a test": one device at a time, with the outcome as a status for the polite live region. After a 429 the
 * button rests for as long as the API asked, then comes back by itself.
 */
export function useTestPush(
  devices: readonly NotificationDevice[] | undefined,
  currentId: string | null,
  onGone: () => void,
) {
  const [status, setStatus] = useState<TestStatus>({ kind: 'idle' })
  const timer = useRef<number | undefined>(undefined)
  // Two taps can land before React re-renders; the ref closes that gap.
  const inFlight = useRef(false)
  const target = pickTestDevice(devices ?? [], currentId)
  const mutation = useMutation({ mutationFn: (id: string) => sendTestPush(id) })

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const resting = status.kind === 'sending' || status.kind === 'rate_limited'
  const send = useCallback(() => {
    if (!target || resting || inFlight.current) return
    inFlight.current = true
    setStatus({ kind: 'sending' })
    notificationAnalytics.testRequested(target.platform)
    mutation.mutate(target.id, {
      onSuccess: () => setStatus({ kind: 'sent' }),
      onError: (error) => {
        const next = statusFromError(error)
        setStatus(next)
        if (next.kind === 'device_gone') onGone()
        if (next.kind === 'rate_limited') {
          window.clearTimeout(timer.current)
          timer.current = window.setTimeout(() => setStatus({ kind: 'idle' }), next.seconds * 1000)
        }
      },
      onSettled: () => {
        inFlight.current = false
      },
    })
  }, [target, resting, mutation, onGone])

  return { status, send, canSend: target !== null && !resting, target }
}
