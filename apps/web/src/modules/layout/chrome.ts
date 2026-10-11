/**
 * Which parts of the site frame a route draws, set with `staticData` on the route.
 *
 * - `chrome: 'bare'` draws nothing but the page. For pages in their own small window, like the fallback timer (X-01 W4.4).
 * - `footer: true` draws the site footer. The footer is for static public content (landing, courses, features) and is
 *   opt-in: a page that does not ask for it has none, so workspace screens under `/app`, sign-in and any new page stay
 *   free of it by default. Spread `publicPage` into the route instead of writing the flag by hand.
 */
declare module '@tanstack/react-router' {
  interface StaticDataRouteOption {
    chrome?: 'bare'
    footer?: boolean
  }
}

interface Matched {
  staticData: { chrome?: 'bare'; footer?: boolean }
}

export const isBareChrome = (matches: ReadonlyArray<Matched>): boolean =>
  matches.some((m) => m.staticData.chrome === 'bare')

export const hasFooter = (matches: ReadonlyArray<Matched>): boolean =>
  !isBareChrome(matches) && matches.some((m) => m.staticData.footer === true)

/** `staticData` for a static public page: it gets the site footer (and a signed-in student does not see it). */
export const publicPage = { footer: true } as const
