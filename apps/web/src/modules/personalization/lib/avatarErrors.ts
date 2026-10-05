import { ApiError } from '~/lib/api'

export type UploadFailure = 'type' | 'size' | 'small' | 'network' | 'server' | 'rate_limited'

/** Maps an upload error to the analytics reason and the sentence the dialog shows (PRD 5.5 states table). */
export function describeUploadError(error: unknown): { reason: UploadFailure; message: string } {
  if (error instanceof ApiError) {
    if (error.status === 429) {
      const minutes = error.retryAfter ? Math.max(1, Math.ceil(error.retryAfter / 60)) : null
      return {
        reason: 'rate_limited',
        message: minutes
          ? `Too many changes. Try again in ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}.`
          : 'Too many changes. Try again in a little while.',
      }
    }
    switch (error.code) {
      case 'invalid_image':
        return { reason: 'type', message: 'Use a JPG, PNG or WebP image.' }
      case 'image_too_small':
        return { reason: 'small', message: 'Choose a photo at least 128 by 128 pixels.' }
      case 'image_too_large':
      case 'payload_too_large':
        return { reason: 'size', message: 'That photo is too large. Choose a smaller one.' }
      case 'feature_disabled':
        return { reason: 'server', message: 'Photo upload is not available yet. You can choose an avatar instead.' }
    }
    if (error.status === 0) {
      return { reason: 'network', message: 'We could not save your photo. Check your connection and try again.' }
    }
  }
  return { reason: 'server', message: 'We could not save your photo. Try again.' }
}
