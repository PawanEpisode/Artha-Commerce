/**
 * Whether a route draws the site header and footer. A route opts out with `staticData: { chrome: 'bare' }`, which is
 * for pages that live in their own small window, like the fallback timer (X-01 W4.4).
 */
declare module '@tanstack/react-router' {
  interface StaticDataRouteOption {
    chrome?: 'bare'
  }
}

export const isBareChrome = (matches: ReadonlyArray<{ staticData: { chrome?: 'bare' } }>): boolean =>
  matches.some((m) => m.staticData.chrome === 'bare')
