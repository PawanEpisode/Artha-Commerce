import { ApiError } from '~/lib/api'

export const CONFIRM_WORD = 'DELETE'

/** `artha-data-2026-10-06.json` (the student's own date, so the file name matches their calendar). */
export function exportFileName(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `artha-data-${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}.json`
}

export const exportBlob = (data: unknown): Blob =>
  new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })

/** Saves a Blob through a temporary link, then frees it. Browser only. */
export function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

/** Typed word matches, ignoring case and surrounding spaces (the server still insists on the exact word). */
export const isConfirmed = (typed: string): boolean => typed.trim().toUpperCase() === CONFIRM_WORD

export type AccountFailure = 'reauth' | 'rate_limited' | 'incomplete' | 'network' | 'server'

export function describeAccountError(
  error: unknown,
  action: 'export' | 'delete',
): { kind: AccountFailure; message: string } {
  if (error instanceof ApiError) {
    if (error.code === 'reauth_required') {
      return { kind: 'reauth', message: 'Confirm it is you with a new code first.' }
    }
    if (error.status === 429) {
      return {
        kind: 'rate_limited',
        message:
          action === 'export'
            ? 'You can export your data a few times an hour. Try again later.'
            : 'Too many attempts today. Try again tomorrow.',
      }
    }
    if (error.code === 'deletion_incomplete') {
      return { kind: 'incomplete', message: 'We could not finish deleting your account. Try again.' }
    }
    if (error.status === 0) {
      return { kind: 'network', message: 'We could not reach the server. Check your connection and try again.' }
    }
  }
  return {
    kind: 'server',
    message:
      action === 'export'
        ? 'We could not prepare your data. Try again.'
        : 'We could not delete your account. Try again.',
  }
}
