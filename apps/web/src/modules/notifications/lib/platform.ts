/**
 * What this browser can do about push, decided from facts passed in (pure, so every row of the matrix is a unit test).
 * `browser.ts` reads the facts from the real window.
 */
export type Platform = 'android' | 'ios' | 'windows' | 'macos' | 'linux' | 'other'
export type Browser = 'chrome' | 'edge' | 'firefox' | 'safari' | 'other'
/** `app` is reserved for the desktop companion. */
export type DisplayMode = 'browser' | 'standalone'

/**
 * - `supported`: can subscribe now.
 * - `ios_needs_install`: iPhone or iPad Safari tab. Push only works from a Home Screen app (iOS 16.4+).
 * - `in_app_browser`: opened inside another app (WhatsApp, Instagram...). The student must open it in a real browser.
 * - `unsupported`: no service worker, push or notification support, an insecure page, or iOS older than 16.4.
 */
export type PushSupport = 'supported' | 'ios_needs_install' | 'in_app_browser' | 'unsupported'

export interface EnvironmentFacts {
  userAgent: string
  maxTouchPoints: number
  /** Running as an installed app (display-mode standalone, or `navigator.standalone` on iOS). */
  standalone: boolean
  hasServiceWorker: boolean
  hasPushManager: boolean
  hasNotification: boolean
  isSecureContext: boolean
}

export interface Environment {
  platform: Platform
  browser: Browser
  displayMode: DisplayMode
  /** Name of the app the page is open in, or null in a normal browser. */
  inAppBrowser: string | null
  support: PushSupport
  /** Student-readable name for the device list, for example "Chrome on Android". */
  label: string
}

const IN_APP_PATTERNS: ReadonlyArray<readonly [string, RegExp]> = [
  ['Facebook', /FBAN|FBAV|FB_IAB|FBIOS/],
  ['Instagram', /Instagram/],
  ['WhatsApp', /WhatsApp/],
  ['LinkedIn', /LinkedInApp/],
  ['Snapchat', /Snapchat/],
  ['Line', /\bLine\//],
  ['WeChat', /MicroMessenger/],
  ['TikTok', /musical_ly|BytedanceWebview|TikTok/],
  ['Twitter', /Twitter/],
  ['Pinterest', /Pinterest/],
]

const isIos = (ua: string, touchPoints: number) =>
  /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && touchPoints > 1)

export function detectPlatform(ua: string, touchPoints: number): Platform {
  if (isIos(ua, touchPoints)) return 'ios'
  if (/Android/.test(ua)) return 'android'
  if (/Windows/.test(ua)) return 'windows'
  if (/Macintosh|Mac OS X/.test(ua)) return 'macos'
  if (/CrOS/.test(ua)) return 'other'
  if (/Linux|X11/.test(ua)) return 'linux'
  return 'other'
}

export function detectBrowser(ua: string): Browser {
  if (/EdgiOS|EdgA|Edg\//.test(ua)) return 'edge'
  if (/FxiOS|Firefox/.test(ua)) return 'firefox'
  if (/OPR\/|Opera|OPT\/|SamsungBrowser|UCBrowser|YaBrowser|DuckDuckGo/.test(ua)) return 'other'
  if (/CriOS|Chrome|Chromium/.test(ua)) return 'chrome'
  if (/Safari/.test(ua) && /Version\//.test(ua)) return 'safari'
  return 'other'
}

/** The app a page is open inside, or null. Home Screen apps on iOS also lack "Safari/" in the UA, hence `standalone`. */
export function detectInAppBrowser(ua: string, platform: Platform, standalone: boolean): string | null {
  for (const [name, pattern] of IN_APP_PATTERNS) if (pattern.test(ua)) return name
  if (standalone) return null
  if (platform === 'android' && /; wv\)/.test(ua)) return 'an app'
  const iosWebView =
    platform === 'ios' && /AppleWebKit/.test(ua) && !/Safari\//.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua)
  return iosWebView ? 'an app' : null
}

/** iOS version from the UA (`OS 16_4`), or null when it is not stated (iPadOS in desktop mode). */
export function iosVersion(ua: string): { major: number; minor: number } | null {
  const match = /OS (\d+)[_.](\d+)/.exec(ua)
  return match ? { major: Number(match[1]), minor: Number(match[2]) } : null
}

const iosTooOld = (ua: string) => {
  const version = iosVersion(ua)
  return version !== null && (version.major < 16 || (version.major === 16 && version.minor < 4))
}

const PLATFORM_NAME: Record<Platform, string> = {
  android: 'Android',
  ios: 'iOS',
  windows: 'Windows',
  macos: 'Mac',
  linux: 'Linux',
  other: 'this device',
}
const BROWSER_NAME: Record<Browser, string> = {
  chrome: 'Chrome',
  edge: 'Edge',
  firefox: 'Firefox',
  safari: 'Safari',
  other: 'Browser',
}

export const deviceLabel = (browser: Browser, platform: Platform, displayMode: DisplayMode): string =>
  `${displayMode === 'standalone' ? 'Artha app' : BROWSER_NAME[browser]} on ${PLATFORM_NAME[platform]}`

export function describeEnvironment(facts: EnvironmentFacts): Environment {
  const platform = detectPlatform(facts.userAgent, facts.maxTouchPoints)
  const browser = detectBrowser(facts.userAgent)
  const displayMode: DisplayMode = facts.standalone ? 'standalone' : 'browser'
  const inAppBrowser = detectInAppBrowser(facts.userAgent, platform, facts.standalone)
  const hasApis = facts.isSecureContext && facts.hasServiceWorker && facts.hasPushManager && facts.hasNotification

  let support: PushSupport
  if (inAppBrowser) support = 'in_app_browser'
  else if (platform === 'ios' && iosTooOld(facts.userAgent)) support = 'unsupported'
  // An iOS Safari tab has no PushManager at all, so the install hint must come before the capability check.
  else if (platform === 'ios' && !facts.standalone) support = 'ios_needs_install'
  else support = hasApis ? 'supported' : 'unsupported'

  return { platform, browser, displayMode, inAppBrowser, support, label: deviceLabel(browser, platform, displayMode) }
}
