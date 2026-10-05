/**
 * Kept so a stored session can still be recognised, and so `/app?from=landing` can restore the last visit.
 * `/` itself no longer redirects: a signed-in student stays on the home and sees their course there.
 *
 * The `personalization` flag lives in PostHog, which is not loaded that early, so the app mirrors the flag into one
 * localStorage key whenever it learns it. "off" disables this script; anything else leaves it on.
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
