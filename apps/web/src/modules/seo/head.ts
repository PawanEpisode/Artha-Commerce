import { env, siteUrl } from '~/lib/env'

export const DEFAULT_OG_IMAGE = '/og/default.png'

export interface SeoInput {
  title: string
  description: string
  /** Path beginning with "/". Used for canonical and og:url. */
  path: string
  image?: string
  imageAlt?: string
  type?: 'website' | 'article'
  noindex?: boolean
  jsonLd?: Record<string, unknown> | Array<Record<string, unknown>>
}

const abs = (path: string) => (path.startsWith('http') ? path : `${siteUrl}${path}`)

/**
 * Builds a TanStack Router `head` object with everything link unfurlers need
 * (WhatsApp, iMessage, Slack, LinkedIn, X): title, description, canonical, Open Graph and Twitter card.
 */
export function buildHead({
  title,
  description,
  path,
  image = DEFAULT_OG_IMAGE,
  imageAlt = `${env.VITE_SITE_NAME}: exam preparation workspace for CA, CS and CMA`,
  type = 'website',
  noindex = false,
  jsonLd,
}: SeoInput) {
  const url = abs(path)
  const imageUrl = abs(image)
  const fullTitle = path === '/' ? title : `${title} | ${env.VITE_SITE_NAME}`

  return {
    meta: [
      { title: fullTitle },
      { name: 'description', content: description },
      ...(noindex ? [{ name: 'robots', content: 'noindex, nofollow' }] : []),
      { property: 'og:site_name', content: env.VITE_SITE_NAME },
      { property: 'og:type', content: type },
      { property: 'og:locale', content: 'en_IN' },
      { property: 'og:title', content: fullTitle },
      { property: 'og:description', content: description },
      { property: 'og:url', content: url },
      { property: 'og:image', content: imageUrl },
      { property: 'og:image:width', content: '1200' },
      { property: 'og:image:height', content: '630' },
      { property: 'og:image:alt', content: imageAlt },
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: fullTitle },
      { name: 'twitter:description', content: description },
      { name: 'twitter:image', content: imageUrl },
    ],
    links: [{ rel: 'canonical', href: url }],
    scripts: jsonLd
      ? [{ type: 'application/ld+json', children: JSON.stringify(jsonLd) }]
      : [],
  }
}
