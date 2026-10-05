import { createFileRoute, Outlet } from '@tanstack/react-router'

import { RequireAuth } from '~/modules/auth'
import { MiniTimer } from '~/modules/tracker'

/** Layout for everything under /app: signed-in only. */
export const Route = createFileRoute('/app')({
  component: () => (
    <RequireAuth>
      <Outlet />
      <MiniTimer />
    </RequireAuth>
  ),
})
