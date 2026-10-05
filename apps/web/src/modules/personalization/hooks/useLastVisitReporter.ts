import { useLocation } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'

import { useAuth } from '~/modules/auth'
import { useFeatureFlag } from '~/modules/observability'

import { type ReportMemory, saveLocalVisit, sendVisit, shouldReport } from '../lib/lastVisit'
import { cleanVisit } from '../lib/restorable'

/**
 * Remembers where the student was, only when it matters (PRD 5.6): when the tab is hidden or the page is going away,
 * never on navigation. The current page and token live in refs because `pagehide` cannot wait for anything async.
 */
export function useLastVisitReporter() {
  const enabled = useFeatureFlag('personalization')
  const { session } = useAuth()
  const { pathname, searchStr } = useLocation({ select: (l) => ({ pathname: l.pathname, searchStr: l.searchStr }) })
  const latest = useRef({ pathname, searchStr, token: session?.access_token, userId: session?.user.id })
  latest.current = { pathname, searchStr, token: session?.access_token, userId: session?.user.id }
  const memory = useRef<ReportMemory | null>(null)

  useEffect(() => {
    if (!enabled) return
    function report() {
      const { pathname: path, searchStr: search, token, userId } = latest.current
      const visit = cleanVisit(path, search)
      if (!visit || !token || !userId) return
      saveLocalVisit(userId, visit)
      const now = Date.now()
      if (!shouldReport(memory.current, visit, now)) return
      memory.current = { href: `${visit.path}?${visit.search}`, at: now }
      sendVisit(token, visit)
    }
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') report()
    }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pagehide', report)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pagehide', report)
    }
  }, [enabled])
}
