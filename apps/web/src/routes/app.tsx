import { createFileRoute, Outlet } from '@tanstack/react-router'

import { RequireAuth } from '~/modules/auth'

/** Layout for everything under /app: signed-in only. */
export const Route = createFileRoute('/app')({
  component: () => (
    <RequireAuth>
      <Outlet />
    </RequireAuth>
  ),
})
