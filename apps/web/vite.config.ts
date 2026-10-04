import { sentryVitePlugin } from '@sentry/vite-plugin'
import tailwindcss from '@tailwindcss/vite'
import { tanstackStart } from '@tanstack/react-start/plugin/vite'
import viteReact from '@vitejs/plugin-react'
import { nitro } from 'nitro/vite'
import { createLogger, defineConfig, loadEnv } from 'vite'

// "use client" directives in motion/radix/react-query are meaningless outside RSC; keep them out of build logs.
const logger = createLogger()
const warn = logger.warn
logger.warn = (msg, options) => {
  if (msg.includes('MODULE_LEVEL_DIRECTIVE')) return
  warn(msg, options)
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const uploadSourcemaps = Boolean(env.SENTRY_AUTH_TOKEN && env.SENTRY_ORG && env.SENTRY_PROJECT)

  return {
    customLogger: logger,
    server: { port: 3000 },
    resolve: { tsconfigPaths: true },
    // The design system ships as TypeScript source; bundle it for SSR instead of treating it as an external dependency.
    ssr: { noExternal: ['@artha/design-system'] },
    build: {
      sourcemap: uploadSourcemaps ? 'hidden' : false,
    },
    plugins: [
      tailwindcss(),
      tanstackStart(),
      nitro(),
      viteReact(),
      // Uploads source maps to Sentry only when credentials exist (Vercel production builds).
      ...(uploadSourcemaps
        ? [
            sentryVitePlugin({
              org: env.SENTRY_ORG,
              project: env.SENTRY_PROJECT,
              authToken: env.SENTRY_AUTH_TOKEN,
              sourcemaps: { filesToDeleteAfterUpload: ['**/*.map'] },
            }),
          ]
        : []),
    ],
  }
})
