/**
 * The icon badge of the installed app (X-01 W4.5, FR-C8): a plain dot, never a number, while a timer runs. The Badging
 * API exists in installed Chrome, Edge and Safari apps; everywhere else it is simply absent and nothing happens.
 */
export const badgeWanted = ({ flagOn, live }: { flagOn: boolean; live: string }): boolean =>
  flagOn && (live === 'pomodoro' || live === 'stopwatch')

type BadgeNavigator = Partial<Pick<Navigator, 'setAppBadge' | 'clearAppBadge'>>

/** Sets or clears the dot. Feature-detected, and a refusal (a browser that only allows it for installed apps) is ignored. */
export function applyAppBadge(
  on: boolean,
  nav: BadgeNavigator | null = typeof navigator === 'undefined' ? null : navigator,
) {
  try {
    const result = on ? nav?.setAppBadge?.() : nav?.clearAppBadge?.()
    void Promise.resolve(result).catch(() => undefined)
  } catch {
    // The badge is a nicety: a throw must never reach the timer.
  }
}
