import { createFileRoute } from '@tanstack/react-router'

import { buildRobotsTxt } from '~/modules/seo'

export const Route = createFileRoute('/robots.txt')({
  server: {
    handlers: {
      GET: () =>
        new Response(buildRobotsTxt(), {
          headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'public, max-age=3600' },
        }),
    },
  },
})
