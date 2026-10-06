/** Messages the worker posts to open pages. Shared so the two sides cannot disagree on a name. */
export const SW_MESSAGE_SUBSCRIPTION_CHANGED = 'artha:push-subscription-changed'

export interface SubscriptionChangedMessage {
  type: typeof SW_MESSAGE_SUBSCRIPTION_CHANGED
  /** The worker got a new subscription; the page must register it with the API. */
  resubscribed: boolean
}

export const isSubscriptionChangedMessage = (data: unknown): data is SubscriptionChangedMessage =>
  typeof data === 'object' &&
  data !== null &&
  (data as { type?: unknown }).type === SW_MESSAGE_SUBSCRIPTION_CHANGED &&
  typeof (data as { resubscribed?: unknown }).resubscribed === 'boolean'
