import { z } from 'zod'

/**
 * Typed, validated access to public (browser-safe) environment variables.
 * Every VITE_* variable the app reads must be declared here: one place, one contract.
 */
const schema = z.object({
  VITE_SITE_URL: z.string().url().default('http://localhost:3000'),
  VITE_SITE_NAME: z.string().default('ArthaCommerce'),
  VITE_SUPABASE_URL: z.string().optional(),
  VITE_SUPABASE_ANON_KEY: z.string().optional(),
  VITE_API_URL: z.string().default('http://localhost:8000'),
  VITE_POSTHOG_KEY: z.string().optional(),
  VITE_POSTHOG_HOST: z.string().default('/ingest'),
  VITE_POSTHOG_UI_HOST: z.string().default('https://us.posthog.com'),
  VITE_SENTRY_DSN: z.string().optional(),
})

const parsed = schema.safeParse(import.meta.env)

if (!parsed.success) {
  console.error('Invalid environment variables', parsed.error.flatten().fieldErrors)
}

export const env = parsed.success ? parsed.data : schema.parse({})

export const siteUrl = env.VITE_SITE_URL.replace(/\/$/, '')
