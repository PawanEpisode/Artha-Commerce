import { siteUrl } from '~/lib/env'

/** Paths crawlers must not fetch. `/og/` stays open: link unfurlers (WhatsApp, X, LinkedIn) fetch preview images there. */
export const DISALLOWED_PATHS = ['/app', '/auth/', '/design-system']

/** Social crawlers are named so a future blanket rule can never block them by accident. */
const SOCIAL_BOTS = ['WhatsApp', 'facebookexternalhit', 'Twitterbot', 'LinkedInBot', 'Slackbot']

export function buildRobotsTxt(): string {
  const disallow = DISALLOWED_PATHS.map((p) => `Disallow: ${p}`).join('\n')
  const social = SOCIAL_BOTS.map((bot) => `User-agent: ${bot}\nAllow: /\n${disallow}`).join('\n\n')
  return `User-agent: *\nAllow: /\n${disallow}\n\n${social}\n\nSitemap: ${siteUrl}/sitemap.xml\n`
}
