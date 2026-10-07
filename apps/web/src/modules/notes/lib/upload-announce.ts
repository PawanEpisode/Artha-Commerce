import { type UploadItem, uploadPercent } from './upload-manager'

/**
 * The sentence for the chip's live region when an upload moves on, or null when nothing worth saying changed. It speaks
 * at the start, every quarter of the transfer, and at each phase change, so a screen reader is informed, not flooded.
 */
export function announceChange(prev: UploadItem | undefined, next: UploadItem): string | null {
  const name = next.fileName
  if (!prev) return `Uploading ${name}.`
  if (prev.phase !== next.phase) {
    switch (next.phase) {
      case 'uploading':
        return `Uploading ${name}.`
      case 'processing':
        return `${name} uploaded. Checking the file.`
      case 'ready':
        return `${name} is ready.`
      case 'duplicate':
        return `You already have ${name}. Open it or keep both.`
      case 'failed':
        return `${name}: ${next.failure?.message ?? 'The upload failed.'}`
      default:
        return null
    }
  }
  const before = uploadPercent(prev)
  const after = uploadPercent(next)
  if (
    before !== null &&
    after !== null &&
    next.phase === 'uploading' &&
    Math.floor(after / 25) > Math.floor(before / 25)
  )
    return `${name}: ${Math.floor(after / 25) * 25} percent uploaded.`
  return null
}
