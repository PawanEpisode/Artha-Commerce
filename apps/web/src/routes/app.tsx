import { createFileRoute, Outlet } from '@tanstack/react-router'

import { RequireAuth } from '~/modules/auth'
import { NotificationsAppEffects } from '~/modules/notifications'
import { LastVisitReporter, RequireOnboarded } from '~/modules/personalization'

/** Layout for everything under /app: signed-in only, and onboarded when the personalization flag is on. The corner timer lives in the root layout so every route can show it. */
export const Route = createFileRoute('/app')({
  component: () => (
    <RequireAuth>
      <RequireOnboarded>
        <LastVisitReporter />
        <NotificationsAppEffects />
        <Outlet />
      </RequireOnboarded>
    </RequireAuth>
  ),
})
