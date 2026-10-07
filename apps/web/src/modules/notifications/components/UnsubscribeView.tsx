import { Button, CircleAlert, CircleCheck, EmptyState, Mail } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { UnsubscribeStatus } from '../lib/unsubscribe'

interface Props {
  status: UnsubscribeStatus
  /** The name of the email being switched off ("Weekly summary"), once the link has been checked. */
  label?: string
  onConfirm: () => void
}

const SETTINGS = '/app/settings/notifications'

/** Every state has an icon and words, never colour alone. One button, so a single click does it. */
export function UnsubscribeView({ status, label, onConfirm }: Props) {
  const what = label ? label.toLowerCase() : 'this email'
  if (status === 'done') {
    return (
      <EmptyState
        role="status"
        icon={<CircleCheck aria-hidden />}
        title="You are unsubscribed"
        description={`We will not send the ${what} by email any more. You can turn it back on in your notification settings.`}
        action={
          <Button asChild variant="outline">
            <Link to={SETTINGS}>Notification settings</Link>
          </Button>
        }
      />
    )
  }
  if (status === 'invalid') {
    return (
      <EmptyState
        icon={<CircleAlert aria-hidden />}
        title="This link is not valid"
        description="It may have been cut short when it was copied. You can switch emails off any time in your notification settings."
        action={
          <Button asChild variant="outline">
            <Link to={SETTINGS}>Notification settings</Link>
          </Button>
        }
      />
    )
  }
  if (status === 'error') {
    return (
      <EmptyState
        role="alert"
        icon={<CircleAlert aria-hidden />}
        title="That did not work"
        description="We could not reach Artha just now. Nothing has changed. Please try again."
        action={<Button onClick={onConfirm}>Try again</Button>}
      />
    )
  }
  const busy = status === 'checking' || status === 'working'
  return (
    <EmptyState
      icon={<Mail aria-hidden />}
      title={`Unsubscribe from the ${what}?`}
      description="One click and we stop sending it. Your study data and your other notifications stay as they are."
      action={
        <Button onClick={onConfirm} disabled={busy} aria-busy={busy}>
          {status === 'working' ? 'Unsubscribing' : 'Unsubscribe'}
        </Button>
      }
    />
  )
}
