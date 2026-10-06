import { Bell, EmptyState } from '@artha/design-system'

/** Shown instead of a notifications screen while the feature is off for this student (flag or server). */
export function NotificationsOff() {
  return (
    <EmptyState
      icon={<Bell aria-hidden />}
      title="Notifications are not available yet"
      description="We are rolling them out gradually. Everything else in Artha works as usual. Please check back soon."
    />
  )
}
