import { useEffect, useRef } from 'react'

export interface ShortcutHandlers {
  flip?: () => void
  undo?: () => void
  edit?: () => void
  suspend?: () => void
  bury?: () => void
  help?: () => void
}

const isTyping = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName))

/** A control that already reacts to Space and Enter itself: pressing them there must not also run the page shortcut. */
const isControl = (t: EventTarget | null) =>
  t instanceof HTMLElement && t.closest('button, a[href], [role="button"]') !== null

/**
 * The review screen's keys: Space or Enter turn the card, U undo, E edit, S suspend, B bury, ? help. 1 to 4 belong to the
 * rating buttons. Nothing fires with Ctrl, Meta or Alt held, while typing in a field, or while a dialog is open.
 */
export function useShortcuts(handlers: ShortcutHandlers, enabled = true) {
  const ref = useRef(handlers)
  ref.current = handlers
  useEffect(() => {
    if (!enabled) return
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat || isTyping(e.target)) return
      if (document.querySelector('[role="dialog"]')) return
      const h = ref.current
      const key = e.key
      if (key === ' ' || key === 'Enter') {
        if (isControl(e.target) || !h.flip) return
        e.preventDefault()
        h.flip()
        return
      }
      const run = (fn?: () => void) => {
        if (!fn) return
        e.preventDefault()
        fn()
      }
      switch (key.toLowerCase()) {
        case 'u':
          return run(h.undo)
        case 'e':
          return run(h.edit)
        case 's':
          return run(h.suspend)
        case 'b':
          return run(h.bury)
        case '?':
          return run(h.help)
        default:
          return
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [enabled])
}
