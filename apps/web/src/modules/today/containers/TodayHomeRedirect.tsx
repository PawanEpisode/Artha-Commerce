import { Navigate } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { useTodayFlag } from '../hooks/useTodayFlag'

/**
 * `/app` sends a student to Today once the `today_plan` flag is on. With the flag off (or still unknown: it is strict) the
 * workspace home renders as before, so there is no redirect and no loop. `/app/today` never links back here by redirect:
 * its "back to workspace" link is explicit.
 */
export function TodayHomeRedirect({ children, skip = false }: { children: ReactNode; skip?: boolean }) {
  const on = useTodayFlag()
  if (on && !skip) return <Navigate to="/app/today" search={{ from: 'workspace' }} replace />
  return <>{children}</>
}
