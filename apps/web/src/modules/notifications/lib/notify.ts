import { toast, toastApiError } from '@artha/design-system'

import type { EnableOutcome } from './enable'
import { MAX_ACTIVE_DEVICES } from './limits'

/** The one place that words every notification-settings outcome. Toasts say what happened; field problems stay inline. */
const ID = { saved: 'notifications-saved', enable: 'notifications-enable', device: 'notifications-device' } as const

export const notify = {
  saved: () => toast.success('Saved', { id: ID.saved }),
  deviceRemoved: () => toast.success('Device removed', { id: ID.device }),
  error: (error: unknown, fallback: string) => toastApiError(error, fallback),

  /** What happened when the student tried to turn alerts on. `enabled` is the only success. */
  enableOutcome: (outcome: EnableOutcome) => {
    const options = { id: ID.enable }
    switch (outcome.status) {
      case 'enabled':
        return toast.success('Alerts are on for this device', options)
      case 'denied':
      case 'blocked':
        return toast.warning('Alerts are blocked for this site', {
          ...options,
          description: 'You can change this in your browser settings, then check again here.',
        })
      case 'dismissed':
        return toast.info('No problem', { ...options, description: 'You can turn alerts on whenever you like.' })
      case 'unsupported':
        return toast.info('This browser cannot show alerts', options)
      case 'device_limit':
        return toast.warning('You have too many devices', {
          ...options,
          description: `You can have up to ${MAX_ACTIVE_DEVICES}. Remove one below, then try again.`,
        })
      case 'error':
        return toast.error('We could not turn alerts on', {
          ...options,
          description:
            outcome.reason === 'bad_key'
              ? 'Alerts are not set up correctly in this version of the app.'
              : 'Please try again in a moment.',
        })
    }
  },
}
