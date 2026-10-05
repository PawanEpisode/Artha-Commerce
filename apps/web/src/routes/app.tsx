import { createFileRoute, Outlet } from '@tanstack/react-router'

import { RequireAuth } from '~/modules/auth'

/** Layout for everything under /app: signed-in only. The corner timer lives in the root layout so every route can show it. */
export const Route = createFileRoute('/app')({
  component: () => (
    <RequireAuth>
      <Outlet />
    </RequireAuth>
  ),
})
