export type ShortcutAction = 'toggle' | 'skip' | 'end'

/**
 * Space starts, pauses or resumes; S skips a break; E ends a round early. Typing in a field or pressing a control that
 * already uses the key (Space on a button) is left alone, as are keys with a modifier. Pure.
 */
export function shortcutFor(
  e: {
    key: string
    ctrlKey?: boolean
    metaKey?: boolean
    altKey?: boolean
    target?: EventTarget | { tagName?: string; isContentEditable?: boolean } | null
  },
  opts: { dialogOpen: boolean },
): ShortcutAction | null {
  if (opts.dialogOpen || e.ctrlKey || e.metaKey || e.altKey) return null
  const el = e.target as { tagName?: string; isContentEditable?: boolean } | null | undefined
  const tag = el?.tagName?.toUpperCase()
  if (el?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag ?? '')) return null
  if (['BUTTON', 'A'].includes(tag ?? '') && e.key === ' ') return null
  if (e.key === ' ') return 'toggle'
  if (e.key.toLowerCase() === 's') return 'skip'
  if (e.key.toLowerCase() === 'e') return 'end'
  return null
}
