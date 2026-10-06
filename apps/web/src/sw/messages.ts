/** Messages the worker posts to open pages. Shared so the two sides cannot disagree on a name. */
export const SW_MESSAGE_SUBSCRIPTION_CHANGED = 'artha:push-subscription-changed'
export const SW_MESSAGE_PUSH_RECEIVED = 'artha:push-received'

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

/** A push was just shown. It says nothing about the notification: the page asks the API for the inbox instead. */
export interface PushReceivedMessage {
  type: typeof SW_MESSAGE_PUSH_RECEIVED
}

export const isPushReceivedMessage = (data: unknown): data is PushReceivedMessage =>
  typeof data === 'object' && data !== null && (data as { type?: unknown }).type === SW_MESSAGE_PUSH_RECEIVED
