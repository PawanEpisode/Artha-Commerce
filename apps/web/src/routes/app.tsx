import { createFileRoute, Outlet } from '@tanstack/react-router'

import { RequireAuth } from '~/modules/auth'
import { AppShell } from '~/modules/layout'
import { UploadProgressContainer } from '~/modules/notes'
import { NotificationsAppEffects } from '~/modules/notifications'
import { LastVisitReporter, RequireOnboarded } from '~/modules/personalization'

/** Layout for everything under /app: signed-in only, and onboarded when the personalization flag is on. The corner timer lives in the root layout so every route can show it. */
export const Route = createFileRoute('/app')({
  // The frame (sidebar, topbar) is drawn here, so the root shell skips the public header and footer.
  staticData: { chrome: 'app' },
  component: () => (
    <RequireAuth>
      <RequireOnboarded>
        <LastVisitReporter />
        <NotificationsAppEffects />
        <UploadProgressContainer />
        <AppShell>
          <Outlet />
        </AppShell>
      </RequireOnboarded>
    </RequireAuth>
  ),
})
