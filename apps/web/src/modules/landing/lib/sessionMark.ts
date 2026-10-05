/** Hides the guest home once the root script has marked a stored session. The nodes stay in the HTML for crawlers. */
export const SIGNED_IN_MARK_CSS = `[data-study-pending]{display:none}html[data-signed-in="1"] [data-marketing-home]{display:none}html[data-signed-in="1"] [data-study-pending]{display:block}`
