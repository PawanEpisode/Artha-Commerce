/**
 * Marks a stored Supabase session on `<html>` before first paint. Pages use it to hide guest-only chrome
 * (the Courses link, the marketing home) without changing the HTML a crawler or a signed-out visitor receives.
 */
export const SIGNED_IN_MARK_SCRIPT = `(function(){try{for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);if(/^sb-.+-auth-token$/.test(k)){var v=JSON.parse(localStorage.getItem(k)||'null');if(v&&v.access_token&&v.refresh_token){document.documentElement.dataset.signedIn='1';return}}}}catch(e){}})()`
