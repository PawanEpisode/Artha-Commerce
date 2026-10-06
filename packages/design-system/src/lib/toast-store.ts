/**
 * Framework-free toast store. The `toast` object is the imperative API; `<Toaster />` subscribes to it.
 * Keeping state here (not in React) lets any module toast from event handlers, mutations and non-React code.
 */

export type ToastVariant = 'success' | 'error' | 'warning' | 'info' | 'loading' | 'default'

export interface ToastAction {
  label: string
  onClick: () => void
}

export interface ToastOptions {
  /** Same id = update the existing toast instead of stacking a duplicate. */
  id?: string
  description?: string
  action?: ToastAction
  /** Milliseconds; `Infinity` keeps it until dismissed. Defaults per variant (errors stay longest). */
  duration?: number
  /** Replaces the variant icon (custom toasts). */
  icon?: unknown
}

export interface ToastRecord {
  id: string
  variant: ToastVariant
  title: string
  description?: string
  action?: ToastAction
  duration: number
  icon?: unknown
  /** Bumps on every update so timers restart. */
  revision: number
  dismissed: boolean
}

export const DEFAULT_DURATION: Record<ToastVariant, number> = {
  success: 4_000,
  info: 5_000,
  default: 5_000,
  warning: 7_000,
  error: 10_000,
  loading: Number.POSITIVE_INFINITY,
}

/** Most toasts shown at once; older ones are dropped. */
export const MAX_VISIBLE = 4

type Listener = () => void

let records: ToastRecord[] = []
let counter = 0
const listeners = new Set<Listener>()
const showListeners = new Set<(record: ToastRecord) => void>()

function emit(next: ToastRecord[]) {
  records = next
  listeners.forEach((l) => l())
}

export const toastStore = {
  subscribe(listener: Listener) {
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  },
  getSnapshot: () => records,
  /** Observes every toast that is shown or updated (analytics). Receives the record; returns an unsubscribe. */
  onShow(listener: (record: ToastRecord) => void) {
    showListeners.add(listener)
    return () => {
      showListeners.delete(listener)
    }
  },
  /** Physically remove a toast (after its exit animation). */
  remove(id: string) {
    emit(records.filter((r) => r.id !== id))
  },
  reset() {
    counter = 0
    emit([])
  },
}

function push(variant: ToastVariant, title: string, options: ToastOptions = {}): string {
  const id = options.id ?? `toast-${++counter}`
  const existing = records.find((r) => r.id === id)
  const record: ToastRecord = {
    id,
    variant,
    title,
    description: options.description,
    action: options.action,
    icon: options.icon,
    duration: options.duration ?? DEFAULT_DURATION[variant],
    revision: (existing?.revision ?? 0) + 1,
    dismissed: false,
  }
  if (existing) {
    emit(records.map((r) => (r.id === id ? record : r)))
  } else {
    const live = records.filter((r) => !r.dismissed)
    const overflow = live.length >= MAX_VISIBLE ? live.slice(0, live.length - MAX_VISIBLE + 1).map((r) => r.id) : []
    emit([...records.filter((r) => !overflow.includes(r.id)), record])
  }
  // A loading toast is only a placeholder for the result that follows it.
  if (variant !== 'loading') showListeners.forEach((l) => l(record))
  return id
}

type Message<T> = string | ((value: T) => string)
const resolve = <T>(m: Message<T>, value: T) => (typeof m === 'function' ? m(value) : m)

export interface PromiseMessages<T> {
  loading: string
  success: Message<T>
  error: Message<unknown>
}

/**
 * Typed imperative API.
 *
 *   toast.success('Goals saved')
 *   toast.error('Could not save', { description: 'Check your connection.' })
 *   toast.success('Session deleted', { action: { label: 'Undo', onClick: undo } })
 *   toast.promise(save(), { loading: 'Saving…', success: 'Saved', error: 'Could not save' })
 */
export const toast = {
  success: (title: string, options?: ToastOptions) => push('success', title, options),
  error: (title: string, options?: ToastOptions) => push('error', title, options),
  warning: (title: string, options?: ToastOptions) => push('warning', title, options),
  info: (title: string, options?: ToastOptions) => push('info', title, options),
  /** Neutral toast; pass `icon` for something special (celebration, upload). */
  custom: (title: string, options?: ToastOptions) => push('default', title, options),
  promise<T>(
    promise: Promise<T>,
    messages: PromiseMessages<T>,
    options: Omit<ToastOptions, 'duration'> = {},
  ): Promise<T> {
    const id = push('loading', messages.loading, { ...options, id: options.id })
    promise.then(
      (value) => void push('success', resolve(messages.success, value), { id }),
      (error: unknown) => void push('error', resolve(messages.error, error), { id }),
    )
    return promise
  },
  /** Dismiss one toast, or all of them when no id is given. */
  dismiss(id?: string) {
    emit(records.map((r) => (id === undefined || r.id === id ? { ...r, dismissed: true } : r)))
  },
}
