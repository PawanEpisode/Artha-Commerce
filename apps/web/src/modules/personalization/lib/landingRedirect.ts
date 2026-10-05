/**
 * Signed-in students who open `/` go straight to their workspace (FR-F16-31); `/app?from=landing` then lets the destination rules pick the last visit. The page is server-rendered and cached,
 * so the check is a tiny inline script in the head: it runs before the hero paints, reads only the Supabase session
 * key that already sits in localStorage, and changes nothing in the HTML a crawler or a signed-out visitor receives.
 *
 * The `personalization` flag lives in PostHog, which is not loaded that early, so the app mirrors the flag into one
 * localStorage key whenever it learns it. "off" disables the redirect; anything else leaves it on.
 */
export const LANDING_REDIRECT_KEY = 'artha.landing-redirect'

export const LANDING_REDIRECT_SCRIPT = `(function(){try{if(localStorage.getItem('${LANDING_REDIRECT_KEY}')==='off')return;for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);if(/^sb-.+-auth-token$/.test(k)){var v=JSON.parse(localStorage.getItem(k)||'null');if(v&&v.access_token&&v.refresh_token){location.replace('/app?from=landing');return}}}}catch(e){}})()`

export function mirrorLandingRedirect(enabled: boolean): void {
  try {
    if (enabled) localStorage.removeItem(LANDING_REDIRECT_KEY)
    else localStorage.setItem(LANDING_REDIRECT_KEY, 'off')
  } catch {
    // Storage blocked: the redirect stays on, which is the default.
  }
}
