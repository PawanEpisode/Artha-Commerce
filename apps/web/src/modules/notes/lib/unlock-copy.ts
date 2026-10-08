import { ApiError } from '~/lib/api'

import type { DocumentSummary } from './document-types'
import { errorCode } from './errors'

type UnlockDoc = Pick<DocumentSummary, 'status' | 'unlock_status' | 'unlock_reason' | 'is_encrypted' | 'text_status'>

/** Unlock for search is offered for a PDF whose pages cannot be read without its password. */
export const canUnlock = (doc: UnlockDoc) =>
  doc.status === 'needs_password' && doc.unlock_status !== 'waiting' && doc.unlock_status !== 'running'

export const isUnlocking = (doc: Pick<UnlockDoc, 'unlock_status'>) =>
  doc.unlock_status === 'waiting' || doc.unlock_status === 'running'

/** Where a locked PDF stands, in words. `null` when there is nothing to say. */
export function unlockStatusText(doc: UnlockDoc): string | null {
  if (isUnlocking(doc)) return 'Reading the PDF with your password…'
  if (doc.unlock_status === 'done') return 'This PDF is searchable now. Your password was not kept.'
  if (doc.unlock_status === 'failed') {
    switch (doc.unlock_reason) {
      case 'wrong_password':
        return 'That password did not open the PDF. Check it and try again.'
      case 'restricted':
        return 'The owner of this PDF does not allow its text to be copied, so it cannot be made searchable.'
      case 'expired':
        return 'That took too long and the password was discarded. Try again.'
      default:
        return 'We could not read this PDF. Try again.'
    }
  }
  if (doc.status === 'needs_password') return 'This PDF is locked, so its text cannot be searched yet.'
  return null
}

/** What a refused request means to the student (the request itself never succeeded, so nothing was queued). */
export function unlockErrorText(error: unknown): string {
  const code = errorCode(error)
  switch (code) {
    case 'too_many_attempts':
      return 'Too many wrong passwords. Try again in an hour.'
    case 'unlock_unavailable':
      return 'Searching locked PDFs is not available yet.'
    case 'unlock_in_progress':
      return 'We are already reading this PDF.'
    case 'not_locked':
      return 'This PDF does not need a password to be searched.'
    default:
      return error instanceof ApiError && error.status === 0
        ? 'You are offline. Connect to the internet to unlock.'
        : 'Could not start that. Try again.'
  }
}
