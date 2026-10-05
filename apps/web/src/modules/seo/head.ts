import { env, siteUrl } from '~/lib/env'

export const DEFAULT_OG_IMAGE = '/og/default.png'
export const OG_IMAGE_SIZE = { width: 1200, height: 630 } as const

/** Search and unfurl limits. Titles over ~60 and descriptions over ~155 characters are cut by Google and WhatsApp. */
export const TITLE_MAX = 60
export const DESCRIPTION_MAX = 155

export interface SeoInput {
  /** The page's own name. The brand suffix is added for you (except on the home page). */
  title: string
  description: string
  /** Path beginning with "/". Used for canonical and og:url. Query strings and trailing slashes are dropped. */
  path: string
  /** Absolute URL or a path. Must be a 1200x630 image under 300 KB so WhatsApp shows it. */
  image?: string
  imageAlt?: string
  type?: 'website' | 'article'
  /** Private or transactional pages: `noindex, nofollow`. The unfurl preview still works (crawlers ignore robots meta). */
  noindex?: boolean
  jsonLd?: Record<string, unknown> | Array<Record<string, unknown>>
}

export interface HeadTag {
  [key: string]: string | undefined
}

const abs = (path: string) =>
  /^https?:\/\//.test(path) ? path : `${siteUrl}${path.startsWith('/') ? path : `/${path}`}`

/** Canonical form of a path: no query or hash, no trailing slash (except the root). */
export function canonicalPath(path: string): string {
  const clean = path.split(/[?#]/)[0] || '/'
  const withSlash = clean.startsWith('/') ? clean : `/${clean}`
  return withSlash.length > 1 ? withSlash.replace(/\/+$/, '') : '/'
}

/** Cuts at a word boundary and adds an ellipsis when the text is longer than `max`. */
export function fit(text: string, max: number): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (clean.length <= max) return clean
  const cut = clean.slice(0, max - 1)
  const lastSpace = cut.lastIndexOf(' ')
  return `${(lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut).replace(/[\s,;:.-]+$/, '')}…`
}

/** "Features | ArthaCommerce", with the page part shortened so the whole title stays within TITLE_MAX. */
export function composeTitle(title: string, path: string, brand: string = env.VITE_SITE_NAME): string {
  if (canonicalPath(path) === '/') return fit(title, TITLE_MAX)
  const suffix = ` | ${brand}`
  return `${fit(title, TITLE_MAX - suffix.length)}${suffix}`
}

function imageType(url: string): string {
  const ext = url.split(/[?#]/)[0]?.split('.').pop()?.toLowerCase()
  if (ext === 'jpg' || ext === 'jpeg') return 'image/jpeg'
  if (ext === 'webp') return 'image/webp'
  return 'image/png' // static PNGs and the generated /og/... routes
}

/** JSON inside <script> must not be able to close the tag, so `<` is escaped. */
export const serializeJsonLd = (data: unknown) => JSON.stringify(data).replace(/</g, '\\u003c')

/**
 * Builds a TanStack Router `head` object with everything link unfurlers need
 * (WhatsApp, iMessage, Slack, LinkedIn, X): title, description, canonical, Open Graph and Twitter card.
 * Every public route declares `head: () => buildHead(...)`; copy lives in `./pages.ts`.
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
  const canonical = canonicalPath(path)
  const url = abs(canonical)
  const imageUrl = abs(image)
  const fullTitle = composeTitle(title, canonical)
  const text = fit(description, DESCRIPTION_MAX)
  const alt = fit(imageAlt, 200)

  const meta: HeadTag[] = [
    { title: fullTitle },
    { name: 'description', content: text },
    { name: 'robots', content: noindex ? 'noindex, nofollow' : 'index, follow, max-image-preview:large' },
    { property: 'og:site_name', content: env.VITE_SITE_NAME },
    { property: 'og:type', content: type },
    { property: 'og:locale', content: 'en_IN' },
    { property: 'og:title', content: fullTitle },
    { property: 'og:description', content: text },
    { property: 'og:url', content: url },
    { property: 'og:image', content: imageUrl },
    { property: 'og:image:secure_url', content: imageUrl },
    { property: 'og:image:type', content: imageType(imageUrl) },
    { property: 'og:image:width', content: String(OG_IMAGE_SIZE.width) },
    { property: 'og:image:height', content: String(OG_IMAGE_SIZE.height) },
    { property: 'og:image:alt', content: alt },
    { name: 'twitter:card', content: 'summary_large_image' },
    { name: 'twitter:title', content: fullTitle },
    { name: 'twitter:description', content: text },
    { name: 'twitter:image', content: imageUrl },
    { name: 'twitter:image:alt', content: alt },
  ]

  const nodes = jsonLd ? (Array.isArray(jsonLd) ? jsonLd : [jsonLd]) : []
  return {
    meta,
    links: [{ rel: 'canonical', href: url }],
    scripts: nodes.map((node) => ({ type: 'application/ld+json', children: serializeJsonLd(node) })),
  }
}
