import { formatCountdownTime } from '@artha/design-system'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState } from 'react'

import { useAuth } from '~/modules/auth'
import { useLiveTimer } from '~/modules/focus'
import { useFeatureFlag } from '~/modules/observability'

import { PracticeDock } from '../components/PracticeDock'
import { usePracticeClock } from '../hooks/usePracticeClock'
import { getActiveSession } from '../lib/api'
import { type ClockSource, countdownAnnouncement } from '../lib/clock'
import { practiceKeys } from '../lib/keys'
import type { SessionClockView, SessionMode } from '../lib/types'

const MODE_TITLES: Record<SessionMode, string> = {
  untimed: 'Practice',
  timed: 'Timed practice',
  chapter_quiz: 'Chapter quiz',
  revision: 'Revision',
  custom_test: 'Custom test',
  exam: 'Exam simulation',
}

const EXPIRY_CHECK_DELAY_MS = 6500

/** The dock for one running session. Mounted only while there is one, so nothing here costs a page without one. */
function DockHost({
  session,
  receivedAtMs,
  onExpired,
}: {
  session: SessionClockView
  receivedAtMs: number
  /** Called once, shortly after a countdown reaches zero, so the dock asks the server whether the session closed. */
  onExpired: () => void
}) {
  const { live } = useLiveTimer()
  const source: ClockSource = { ...session, receivedAtMs }
  const clock = usePracticeClock(source)

  const seconds = clock && clock.kind !== 'waiting' ? clock.seconds : null
  const countdown = clock?.kind === 'countdown'
  const last = useRef<number | null>(null)
  const [announcement, setAnnouncement] = useState('')
  useEffect(() => {
    if (!countdown || seconds === null) {
      last.current = null
      setAnnouncement('')
      return
    }
    const said = countdownAnnouncement(last.current, seconds)
    last.current = seconds
    if (said) setAnnouncement(said)
  }, [countdown, seconds])

  const expired = clock?.kind === 'countdown' && clock.expired
  useEffect(() => {
    if (!expired) return
    // The server gives a few seconds of grace before it closes the session; ask just after that.
    const id = window.setTimeout(onExpired, EXPIRY_CHECK_DELAY_MS)
    return () => window.clearTimeout(id)
  }, [expired, onExpired])

  if (!clock || clock.kind === 'waiting') return null
  return (
    <PracticeDock
      clock={clock}
      time={formatCountdownTime(clock.seconds)}
      title={MODE_TITLES[session.mode] ?? 'Practice'}
      raised={live !== 'none'}
      announcement={announcement}
      renderLink={(children) => (
        <Link
          to="/app/practice/session/$id"
          params={{ id: session.id }}
          className="rounded-md outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
        >
          {children}
        </Link>
      )}
    />
  )
}

/**
 * Shown on every page while a practice session is running or paused, in the corner like the focus timer (above it when
 * that one is up). The server is the source of truth: the session comes from a small poll, refreshed when the tab
 * regains focus and whenever the player starts, pauses, resumes or submits, and the seconds are counted here.
 */
export function LivePracticeTimer() {
  const { user, loading } = useAuth()
  const queryClient = useQueryClient()
  const enabled = useFeatureFlag('question_bank', { strict: true })
  const active = useQuery({
    queryKey: practiceKeys.active,
    queryFn: getActiveSession,
    enabled: Boolean(user) && enabled,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    staleTime: 15_000,
    retry: 1,
  })

  const checkExpiry = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: practiceKeys.active })
  }, [queryClient])

  if (loading || !user || !enabled || !active.data) return null
  // `key` restarts the announcement memory when the student moves to a different session.
  return (
    <DockHost key={active.data.id} session={active.data} receivedAtMs={active.dataUpdatedAt} onExpired={checkExpiry} />
  )
}
