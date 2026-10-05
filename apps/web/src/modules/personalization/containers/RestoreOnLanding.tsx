import { type ReactNode, useEffect } from 'react'

import { useGoAfterAuth } from '~/modules/auth'

import { WorkspaceSkeleton } from '../components/LoadStates'

/**
 * `/app?from=landing` is where the landing redirect sends a signed-in student: the page decides before anything of
 * the workspace shows, so the last visit is restored without a flash of the home page. Otherwise it is transparent.
 */
export function RestoreOnLanding({ active, children }: { active: boolean; children: ReactNode }) {
  const goAfterAuth = useGoAfterAuth()
  useEffect(() => {
    if (active) void goAfterAuth()
  }, [active, goAfterAuth])
  return active ? <WorkspaceSkeleton /> : <>{children}</>
}
