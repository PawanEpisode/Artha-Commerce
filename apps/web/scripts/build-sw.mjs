// Compiles src/sw/sw.ts into public/sw.js (PRD X-01.1 Q5). Runs before `vite dev` and `vite build`.
// The VAPID public key is public by design; the worker uses it only to re-subscribe after `pushsubscriptionchange`.
import { build } from 'esbuild'
import { loadEnv } from 'vite'

import { swBuildOptions, swVersionFrom } from './sw-build-options.mjs'

const env = { ...loadEnv(process.env.NODE_ENV ?? 'production', process.cwd(), 'VITE_'), ...process.env }

await build(swBuildOptions({ version: swVersionFrom(env), vapidPublicKey: env.VITE_VAPID_PUBLIC_KEY ?? '' }))
