import { defineConfig, loadEnv } from 'vite'
import { tanstackStart } from '@tanstack/react-start/plugin/vite'
import { nitro } from 'nitro/vite'
import viteReact from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { sentryVitePlugin } from '@sentry/vite-plugin'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const uploadSourcemaps = Boolean(env.SENTRY_AUTH_TOKEN && env.SENTRY_ORG && env.SENTRY_PROJECT)

  return {
    server: { port: 3000 },
    resolve: { tsconfigPaths: true },
    build: {
      sourcemap: uploadSourcemaps ? 'hidden' : false,
      rollupOptions: {
        // "use client" directives in motion/radix are meaningless outside RSC; silence the noise.
        onwarn(warning, defaultHandler) {
          if (warning.code === 'MODULE_LEVEL_DIRECTIVE') return
          defaultHandler(warning)
        },
      },
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
