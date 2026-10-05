import { createFileRoute } from '@tanstack/react-router'

import { buildSitemapXml } from '~/modules/seo'
import { fetchSitemapPaths } from '~/modules/syllabus'

export const Route = createFileRoute('/sitemap.xml')({
  server: {
    handlers: {
      GET: async () =>
        new Response(buildSitemapXml(await fetchSitemapPaths()), {
          headers: { 'Content-Type': 'application/xml; charset=utf-8', 'Cache-Control': 'public, max-age=3600' },
        }),
    },
  },
})
