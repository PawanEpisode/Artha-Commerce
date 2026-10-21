import type { ReactNode } from 'react'

/**
 * Legacy wrapper: previously redirected `/app` to `/app/today` when `today_plan` was on.
 * Retained as a pass-through for backwards compatibility.
 */
export function TodayHomeRedirect({ children }: { children: ReactNode; skip?: boolean }) {
  return <>{children}</>
}
