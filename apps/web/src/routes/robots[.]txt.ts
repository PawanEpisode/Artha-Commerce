import { createFileRoute } from '@tanstack/react-router'
import { siteUrl } from '~/lib/env'

export const Route = createFileRoute('/robots.txt')({
  server: {
    handlers: {
      GET: () =>
        new Response(`User-agent: *\nAllow: /\nDisallow: /app\nDisallow: /auth/\n\nSitemap: ${siteUrl}/sitemap.xml\n`, {
          headers: { 'Content-Type': 'text/plain' },
        }),
    },
  },
})
