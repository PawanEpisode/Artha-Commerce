import { createFileRoute } from '@tanstack/react-router'

import { MiniWindowContainer } from '~/modules/focus'
import { buildHead } from '~/modules/seo'

/** The fallback timer window (X-01 W4.4): bare, so there is no header or footer, and never indexed. */
export const Route = createFileRoute('/app/focus/mini')({
  staticData: { chrome: 'bare' },
  head: () =>
    buildHead({
      title: 'Artha timer',
      description: 'The focus timer in a small window.',
      path: '/app/focus/mini',
      noindex: true,
    }),
  component: MiniWindowContainer,
})
