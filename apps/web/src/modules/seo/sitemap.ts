import { siteUrl } from '~/lib/env'
import { courses, features } from '~/modules/catalog'

/** Date this server instance started, i.e. the deploy date. Honest enough for `lastmod`; never "now" on every fetch. */
const DEPLOY_DATE = new Date().toISOString().slice(0, 10)

/** Public, indexable paths. Derived from the catalog so new courses/features appear automatically. */
export function publicPaths(): string[] {
  return [
    '/',
    '/features',
    '/courses',
    ...features.map((f) => `/features/${f.slug}`),
    ...courses.flatMap((c) => [`/courses/${c.slug}`, ...c.levels.map((l) => `/courses/${c.slug}/${l.slug}`)]),
  ]
}

/** `extraPaths` are dynamic public paths (published syllabus subjects and chapters) supplied by the caller. */
export function buildSitemapXml(extraPaths: string[] = [], lastmod: string = DEPLOY_DATE): string {
  const urls = [...new Set([...publicPaths(), ...extraPaths])]
    .map((p) => `  <url><loc>${siteUrl}${p}</loc><lastmod>${lastmod}</lastmod></url>`)
    .join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
}
