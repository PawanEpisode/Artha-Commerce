/**
 * esbuild options for the service worker, shared by `build-sw.mjs` and the test that checks the bundle.
 * One file out (`public/sw.js`), no code splitting, no runtime dependencies.
 */
export function swBuildOptions({
  version = 'dev',
  vapidPublicKey = '',
  apiBaseUrl = '',
  outfile = 'public/sw.js',
  write = true,
} = {}) {
  return {
    entryPoints: ['src/sw/sw.ts'],
    outfile,
    bundle: true,
    minify: true,
    format: 'iife',
    target: 'es2020',
    platform: 'browser',
    legalComments: 'none',
    write,
    logLevel: 'warning',
    define: {
      __SW_VERSION__: JSON.stringify(version),
      __VAPID_PUBLIC_KEY__: JSON.stringify(vapidPublicKey),
      // Where notification buttons send their one-time token (W3.6). The API origin is public, like the app's own.
      __API_BASE_URL__: JSON.stringify(apiBaseUrl),
    },
  }
}

/** Short build id shown in the device list and push logs: the commit on Vercel, `dev` locally. */
export const swVersionFrom = (env) => (env.VERCEL_GIT_COMMIT_SHA ?? 'dev').slice(0, 7) || 'dev'
