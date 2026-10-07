/**
 * The autosave rule: save 2 seconds after typing stops (FR-F03-33), save at once when the student leaves, never run two
 * saves at the same time, and save again afterwards if they typed while one was in flight. Pure scheduling: the timer
 * functions are injected so the rule is tested without waiting.
 */

export const AUTOSAVE_DELAY_MS = 2000

export type AutosaveStatus = 'idle' | 'dirty' | 'saving'

export interface Autosave {
  /** The text changed: (re)start the countdown. */
  touch: () => void
  /** Save now if anything is unsaved (blur, tab hidden, navigating away, the Save button). */
  flush: () => Promise<void>
  /** Drop any pending save, for example after the student discarded the draft. */
  cancel: () => void
  status: () => AutosaveStatus
}

interface Options {
  /** Does the save. A rejection leaves the state dirty so the next touch or flush tries again. */
  save: () => Promise<void>
  delayMs?: number
  setTimer?: (run: () => void, ms: number) => unknown
  clearTimer?: (handle: unknown) => void
}

export function createAutosave({
  save,
  delayMs = AUTOSAVE_DELAY_MS,
  setTimer = (run, ms) => setTimeout(run, ms),
  clearTimer = (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
}: Options): Autosave {
  let timer: unknown = null
  let dirty = false
  let inFlight: Promise<void> | null = null

  const stop = () => {
    if (timer !== null) clearTimer(timer)
    timer = null
  }

  const run = async (): Promise<void> => {
    stop()
    if (inFlight) {
      // A save is running: when it ends, the dirty flag decides whether another one is needed.
      await inFlight
      return dirty ? run() : undefined
    }
    if (!dirty) return
    dirty = false
    inFlight = save()
      .catch(() => {
        dirty = true
      })
      .finally(() => {
        inFlight = null
      })
    await inFlight
    // Typing during the save left the flag set again; its own countdown handles it.
  }

  return {
    touch: () => {
      dirty = true
      stop()
      timer = setTimer(() => void run(), delayMs)
    },
    flush: run,
    cancel: () => {
      stop()
      dirty = false
    },
    status: () => (inFlight ? 'saving' : dirty ? 'dirty' : 'idle'),
  }
}
