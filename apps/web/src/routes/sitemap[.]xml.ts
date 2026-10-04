import { createFileRoute } from '@tanstack/react-router'

import { buildSitemapXml } from '~/modules/seo'

export const Route = createFileRoute('/sitemap.xml')({
  server: {
    handlers: {
      GET: () =>
        new Response(buildSitemapXml(), {
          headers: { 'Content-Type': 'application/xml', 'Cache-Control': 'public, max-age=3600' },
        }),
    },
  },
})
