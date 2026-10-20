import { createFileRoute } from '@tanstack/react-router'

import { fetchAmendmentSitemapPaths } from '~/modules/amendments'
import { buildSitemapXml } from '~/modules/seo'
import { fetchSitemapPaths } from '~/modules/syllabus'

export const Route = createFileRoute('/sitemap.xml')({
  server: {
    handlers: {
      GET: async () => {
        const [syllabusPaths, amendmentPaths] = await Promise.all([fetchSitemapPaths(), fetchAmendmentSitemapPaths()])
        return new Response(buildSitemapXml([...syllabusPaths, ...amendmentPaths]), {
          headers: { 'Content-Type': 'application/xml; charset=utf-8', 'Cache-Control': 'public, max-age=3600' },
        })
      },
    },
  },
})
