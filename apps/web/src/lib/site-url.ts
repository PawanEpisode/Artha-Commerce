/** The public origin of the production site. Used when VITE_SITE_URL is missing or unusable in a production build. */
export const PRODUCTION_SITE_URL = 'https://arthacommerce.meetpawan.com'
export const DEV_SITE_URL = 'http://localhost:3000'

/**
 * Reduces whatever was configured to a bare origin ("https://host"): no path, query, hash or trailing slash.
 *
 * Every absolute URL (canonical, og:url, og:image, sitemap, robots) is built as `origin + "/path"`. If the variable
 * carries a path (a real incident: "https://host/login"), every one of those URLs points at a 404 and link unfurlers
 * such as WhatsApp drop the preview. So a path is never trusted. An unparseable value falls back to a safe default.
 */
export function resolveSiteUrl(raw: string | undefined, production: boolean): string {
  const fallback = production ? PRODUCTION_SITE_URL : DEV_SITE_URL
  const value = raw?.trim()
  if (!value) return fallback
  try {
    if (/^[a-z][a-z0-9+.-]*:\/\//i.test(value) && !/^https?:\/\//i.test(value)) return fallback
    const url = new URL(/^https?:\/\//i.test(value) ? value : `https://${value}`)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return fallback
    // Production previews must be https, and never point at localhost.
    if (production && (url.hostname === 'localhost' || url.hostname === '127.0.0.1')) return fallback
    if (production) url.protocol = 'https:'
    return url.origin
  } catch {
    return fallback
  }
}
