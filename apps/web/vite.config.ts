import { fileURLToPath } from 'node:url'

import { sentryVitePlugin } from '@sentry/vite-plugin'
import tailwindcss from '@tailwindcss/vite'
import { tanstackStart } from '@tanstack/react-start/plugin/vite'
import viteReact from '@vitejs/plugin-react'
import { codeInspectorPlugin } from 'code-inspector-plugin'
import { nitro } from 'nitro/vite'
import { createLogger, defineConfig, loadEnv } from 'vite'

import { swVersionFrom } from './scripts/sw-build-options.mjs'

// TanStack Start renders HTML itself, so the inspector client is injected into the router module.
const codeInspectorTarget = fileURLToPath(new URL('./src/router.tsx', import.meta.url))

// "use client" directives in motion/radix/react-query are meaningless outside RSC; keep them out of build logs.
const logger = createLogger()
const warn = logger.warn
logger.warn = (msg, options) => {
  if (msg.includes('MODULE_LEVEL_DIRECTIVE')) return
  warn(msg, options)
}

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const uploadSourcemaps = Boolean(env.SENTRY_AUTH_TOKEN && env.SENTRY_ORG && env.SENTRY_PROJECT)

  return {
    customLogger: logger,
    server: { port: 3000 },
    // Same short commit id the service worker is built with (scripts/build-sw.mjs), sent with a device registration.
    define: { __APP_BUILD__: JSON.stringify(swVersionFrom(process.env)) },
    resolve: { tsconfigPaths: true },
    // resvg is a native addon. The client prebundler tries to parse its .node binary as text and crashes dev startup.
    optimizeDeps: { exclude: ['@resvg/resvg-js'] },
    // The design system ships as TypeScript source; bundle it for SSR instead of treating it as an external dependency.
    ssr: { noExternal: ['@artha/design-system'], external: ['@resvg/resvg-js', 'satori'] },
    build: {
      sourcemap: uploadSourcemaps ? 'hidden' : false,
    },
    plugins: [
      // Dev server only. Hold Option+Shift (Alt+Shift on Windows) and click an element to open its source.
      ...(command === 'serve'
        ? [
            codeInspectorPlugin({
              bundler: 'vite',
              hotKeys: ['altKey', 'shiftKey'],
              showSwitch: false,
              injectTo: codeInspectorTarget,
            }),
          ]
        : []),
      tailwindcss(),
      tanstackStart(),
      // satori and resvg are loaded at runtime (OG images) and must stay external, with their files traced into the output.
      nitro({ traceDeps: ['satori*', 'harfbuzzjs*', '@resvg/resvg-js*'] }),
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
