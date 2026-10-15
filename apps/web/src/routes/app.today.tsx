import { createFileRoute, Outlet } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'

/** Layout for `/app/today` (the day) and `/app/today/$date` (a preview or a recap). Its children set their own head. */
export const Route = createFileRoute('/app/today')({
  head: () =>
    buildHead({
      title: 'Today',
      description: 'Your tasks for today, paper by paper.',
      path: '/app/today',
      noindex: true,
    }),
  component: Outlet,
})
