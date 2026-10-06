// Replaced by Vite `define` (vite.config.ts) with the short commit id; the same id is baked into `/sw.js`.
declare const __APP_BUILD__: string | undefined

/** Version of this deploy. Sent with a device registration so push logs can tell which worker a device runs. */
export const BUILD_VERSION: string = typeof __APP_BUILD__ === 'string' && __APP_BUILD__ ? __APP_BUILD__ : 'dev'
