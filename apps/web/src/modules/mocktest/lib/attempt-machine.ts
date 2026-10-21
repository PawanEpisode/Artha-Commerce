import type { PaletteStatus } from './types'

export function formatRemaining(ms: number): string {
  if (ms <= 0) return '00:00'
  const totalSeconds = Math.floor(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  const pad = (n: number) => String(n).padStart(2, '0')

  if (hours > 0) {
    return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
  }
  return `${pad(minutes)}:${pad(seconds)}`
}

export function determinePaletteStatus(params: {
  isCurrent: boolean
  isVisited: boolean
  hasAnswer: boolean
  isFlagged: boolean
}): PaletteStatus {
  const { hasAnswer, isFlagged, isVisited } = params

  if (isFlagged && hasAnswer) return 'marked_answered'
  if (isFlagged) return 'marked_for_review'
  if (hasAnswer) return 'answered'
  if (isVisited) return 'not_answered'
  return 'not_visited'
}
