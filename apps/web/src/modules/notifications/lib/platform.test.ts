import { describe, expect, it } from 'vitest'

import {
  describeEnvironment,
  detectBrowser,
  detectInAppBrowser,
  detectPlatform,
  type EnvironmentFacts,
  iosVersion,
} from './platform'

const UA = {
  androidChrome:
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
  androidFirefox: 'Mozilla/5.0 (Android 14; Mobile; rv:127.0) Gecko/127.0 Firefox/127.0',
  androidSamsung:
    'Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/117.0.0.0 Mobile Safari/537.36',
  androidWebView:
    'Mozilla/5.0 (Linux; Android 13; SM-A546E Build/TP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.0.0 Mobile Safari/537.36',
  windowsChrome:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  windowsEdge:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
  windowsFirefox: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
  linuxChrome: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  macSafari:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
  iphoneSafari:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
  iphoneHomeScreen:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
  iphoneOld:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
  iphone163Safari:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Mobile/15E148 Safari/604.1',
  iphone164:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
  iphoneChrome:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.6478.153 Mobile/15E148 Safari/604.1',
  iphoneInstagram:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 330.0.0.12.113 (iPhone14,5; iOS 17_5; en_IN)',
  iphoneBareWebView:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
  androidFacebook:
    'Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.0.0 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/460.0.0.0;]',
  ipadDesktopMode:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
} as const

const facts = (userAgent: string, patch: Partial<EnvironmentFacts> = {}): EnvironmentFacts => ({
  userAgent,
  maxTouchPoints: 0,
  standalone: false,
  hasServiceWorker: true,
  hasPushManager: true,
  hasNotification: true,
  isSecureContext: true,
  ...patch,
})

describe('detectPlatform', () => {
  it.each([
    [UA.androidChrome, 0, 'android'],
    [UA.windowsChrome, 0, 'windows'],
    [UA.macSafari, 0, 'macos'],
    [UA.linuxChrome, 0, 'linux'],
    [UA.iphoneSafari, 5, 'ios'],
    [UA.ipadDesktopMode, 5, 'ios'],
    ['Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36', 0, 'other'],
    ['curl/8', 0, 'other'],
  ] as const)('%s (touch %s) is %s', (ua, touch, expected) => {
    expect(detectPlatform(ua, touch)).toBe(expected)
  })
})

describe('detectBrowser', () => {
  it.each([
    [UA.androidChrome, 'chrome'],
    [UA.windowsChrome, 'chrome'],
    [UA.windowsEdge, 'edge'],
    [UA.windowsFirefox, 'firefox'],
    [UA.androidFirefox, 'firefox'],
    [UA.macSafari, 'safari'],
    [UA.iphoneSafari, 'safari'],
    [UA.iphoneChrome, 'chrome'],
    [UA.androidSamsung, 'other'],
    ['curl/8', 'other'],
  ] as const)('%s is %s', (ua, expected) => {
    expect(detectBrowser(ua)).toBe(expected)
  })
})

describe('detectInAppBrowser', () => {
  it('names well-known apps', () => {
    expect(detectInAppBrowser(UA.iphoneInstagram, 'ios', false)).toBe('Instagram')
    expect(detectInAppBrowser(UA.androidFacebook, 'android', false)).toBe('Facebook')
  })
  it('spots a bare Android WebView and a bare iOS web view, but not a Home Screen app', () => {
    expect(detectInAppBrowser(UA.androidWebView, 'android', false)).toBe('an app')
    expect(detectInAppBrowser(UA.iphoneBareWebView, 'ios', false)).toBe('an app')
    expect(detectInAppBrowser(UA.iphoneHomeScreen, 'ios', true)).toBeNull()
  })
  it('leaves real browsers alone', () => {
    for (const [ua, platform] of [
      [UA.androidChrome, 'android'],
      [UA.iphoneSafari, 'ios'],
      [UA.iphoneChrome, 'ios'],
      [UA.windowsEdge, 'windows'],
    ] as const) {
      expect(detectInAppBrowser(ua, platform, false)).toBeNull()
    }
  })
})

describe('iosVersion', () => {
  it('reads the version when the UA states it', () => {
    expect(iosVersion(UA.iphone164)).toEqual({ major: 16, minor: 4 })
    expect(iosVersion(UA.iphoneSafari)).toEqual({ major: 17, minor: 5 })
  })
  it('is null when it does not', () => {
    expect(iosVersion(UA.ipadDesktopMode)).toBeNull()
  })
})

describe('describeEnvironment: the support matrix', () => {
  const cases: ReadonlyArray<{
    name: string
    input: EnvironmentFacts
    support: string
    label: string
    displayMode?: string
  }> = [
    {
      name: 'Android Chrome',
      input: facts(UA.androidChrome, { maxTouchPoints: 5 }),
      support: 'supported',
      label: 'Chrome on Android',
    },
    {
      name: 'Android Firefox',
      input: facts(UA.androidFirefox, { maxTouchPoints: 5 }),
      support: 'supported',
      label: 'Firefox on Android',
    },
    {
      name: 'Samsung Internet',
      input: facts(UA.androidSamsung, { maxTouchPoints: 5 }),
      support: 'supported',
      label: 'Browser on Android',
    },
    { name: 'Windows Chrome', input: facts(UA.windowsChrome), support: 'supported', label: 'Chrome on Windows' },
    { name: 'Windows Edge', input: facts(UA.windowsEdge), support: 'supported', label: 'Edge on Windows' },
    { name: 'Windows Firefox', input: facts(UA.windowsFirefox), support: 'supported', label: 'Firefox on Windows' },
    { name: 'Linux Chrome', input: facts(UA.linuxChrome), support: 'supported', label: 'Chrome on Linux' },
    { name: 'macOS Safari', input: facts(UA.macSafari), support: 'supported', label: 'Safari on Mac' },
    {
      name: 'installed Chrome app on Windows',
      input: facts(UA.windowsChrome, { standalone: true }),
      support: 'supported',
      label: 'Artha app on Windows',
      displayMode: 'standalone',
    },
    {
      name: 'iPhone Safari tab (no PushManager there)',
      input: facts(UA.iphoneSafari, { maxTouchPoints: 5, hasPushManager: false, hasNotification: false }),
      support: 'ios_needs_install',
      label: 'Safari on iOS',
    },
    {
      name: 'iPhone Chrome tab',
      input: facts(UA.iphoneChrome, { maxTouchPoints: 5, hasPushManager: false }),
      support: 'ios_needs_install',
      label: 'Chrome on iOS',
    },
    {
      name: 'iPad in desktop mode',
      input: facts(UA.ipadDesktopMode, { maxTouchPoints: 5, hasPushManager: false }),
      support: 'ios_needs_install',
      label: 'Safari on iOS',
    },
    {
      name: 'iPhone Home Screen app, iOS 17',
      input: facts(UA.iphoneHomeScreen, { maxTouchPoints: 5, standalone: true }),
      support: 'supported',
      label: 'Artha app on iOS',
      displayMode: 'standalone',
    },
    {
      name: 'iPhone Home Screen app, iOS 16.4',
      input: facts(UA.iphone164, { maxTouchPoints: 5, standalone: true }),
      support: 'supported',
      label: 'Artha app on iOS',
      displayMode: 'standalone',
    },
    {
      name: 'iPhone Home Screen app, iOS 16.3',
      input: facts(UA.iphoneOld, { maxTouchPoints: 5, standalone: true, hasPushManager: false }),
      support: 'unsupported',
      label: 'Artha app on iOS',
      displayMode: 'standalone',
    },
    {
      name: 'iOS older than 16.4 in a tab',
      input: facts(UA.iphone163Safari, { maxTouchPoints: 5, hasPushManager: false }),
      support: 'unsupported',
      label: 'Safari on iOS',
    },
    {
      name: 'Home Screen app whose browser still lacks PushManager',
      input: facts(UA.iphoneHomeScreen, { maxTouchPoints: 5, standalone: true, hasPushManager: false }),
      support: 'unsupported',
      label: 'Artha app on iOS',
      displayMode: 'standalone',
    },
    {
      name: 'Instagram on iPhone',
      input: facts(UA.iphoneInstagram, { maxTouchPoints: 5, hasPushManager: false }),
      support: 'in_app_browser',
      label: 'Browser on iOS',
    },
    {
      name: 'Facebook on Android',
      input: facts(UA.androidFacebook, { maxTouchPoints: 5 }),
      support: 'in_app_browser',
      label: 'Chrome on Android',
    },
    {
      name: 'Android WebView',
      input: facts(UA.androidWebView, { maxTouchPoints: 5 }),
      support: 'in_app_browser',
      label: 'Chrome on Android',
    },
    {
      name: 'desktop browser with no service worker',
      input: facts(UA.windowsChrome, { hasServiceWorker: false }),
      support: 'unsupported',
      label: 'Chrome on Windows',
    },
    {
      name: 'desktop browser with no PushManager',
      input: facts(UA.macSafari, { hasPushManager: false }),
      support: 'unsupported',
      label: 'Safari on Mac',
    },
    {
      name: 'desktop browser with no Notification API',
      input: facts(UA.windowsFirefox, { hasNotification: false }),
      support: 'unsupported',
      label: 'Firefox on Windows',
    },
    {
      name: 'an insecure page',
      input: facts(UA.androidChrome, { isSecureContext: false, maxTouchPoints: 5 }),
      support: 'unsupported',
      label: 'Chrome on Android',
    },
  ]

  it.each(cases)('$name', ({ input, support, label, displayMode }) => {
    const environment = describeEnvironment(input)
    expect(environment.support).toBe(support)
    expect(environment.label).toBe(label)
    expect(environment.displayMode).toBe(displayMode ?? 'browser')
  })

  it('names the app for the in-app browser branch', () => {
    expect(describeEnvironment(facts(UA.iphoneInstagram, { maxTouchPoints: 5 })).inAppBrowser).toBe('Instagram')
    expect(describeEnvironment(facts(UA.windowsChrome)).inAppBrowser).toBeNull()
  })
})
