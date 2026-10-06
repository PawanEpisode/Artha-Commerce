import { z } from 'zod'

import { resolveSiteUrl } from './site-url'

/**
 * Typed, validated access to public (browser-safe) environment variables.
 * Every VITE_* variable the app reads must be declared here: one place, one contract.
 */
const schema = z.object({
  /** Public origin. Normalised by `resolveSiteUrl`, so a stray path or a missing value cannot break link previews. */
  VITE_SITE_URL: z.string().optional(),
  VITE_SITE_NAME: z.string().default('ArthaCommerce'),
  VITE_SUPABASE_URL: z.string().optional(),
  VITE_SUPABASE_ANON_KEY: z.string().optional(),
  VITE_API_URL: z.string().default('http://localhost:8000'),
  VITE_POSTHOG_KEY: z.string().optional(),
  VITE_POSTHOG_HOST: z.string().default('/ingest'),
  VITE_POSTHOG_UI_HOST: z.string().default('https://us.posthog.com'),
  VITE_SENTRY_DSN: z.string().optional(),
  /** Public VAPID key for Web Push (`web-push generate-vapid-keys`). Public by design. Without it, push stays off. */
  VITE_VAPID_PUBLIC_KEY: z.string().optional(),
  /** `true` registers the service worker in `vite dev` too. Production builds always register it. */
  VITE_SW_DEV: z.enum(['true', 'false']).optional(),
})

const parsed = schema.safeParse(import.meta.env)

if (!parsed.success) {
  console.error('Invalid environment variables', parsed.error.flatten().fieldErrors)
}

export const env = parsed.success ? parsed.data : schema.parse({})

/** Bare origin of the public site (https://host, no trailing slash). Build every absolute URL from this. */
export const siteUrl = resolveSiteUrl(env.VITE_SITE_URL, import.meta.env.PROD)

/** True in a production build (not `vite dev`, not tests). */
export const isProduction: boolean = import.meta.env.PROD
