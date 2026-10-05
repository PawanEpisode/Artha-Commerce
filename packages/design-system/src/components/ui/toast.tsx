import * as React from 'react'

import { CircleCheck, CircleX, Info, LoaderCircle, TriangleAlert, X } from '../../icons'
import { apiErrorMessage } from '../../lib/api-error-message'
import { toast, type ToastRecord, toastStore, type ToastVariant } from '../../lib/toast-store'
import { cn } from '../../lib/utils'

export { apiErrorMessage } from '../../lib/api-error-message'
export type { ToastAction, ToastOptions, ToastVariant } from '../../lib/toast-store'
export { toast } from '../../lib/toast-store'

/** Shows a friendly toast for a failed API call (envelope message, status mapping, or your fallback). */
export function toastApiError(error: unknown, fallback: string, options?: { id?: string }) {
  return toast.error(apiErrorMessage(error, fallback), options)
}

const SURFACE: Record<ToastVariant, string> = {
  success: 'border-success-border bg-success-bg text-success-fg',
  error: 'border-error-border bg-error-bg text-error-fg',
  warning: 'border-warning-border bg-warning-bg text-warning-fg',
  info: 'border-info-border bg-info-bg text-info-fg',
  loading: 'border-border bg-popover text-popover-foreground',
  default: 'border-border bg-popover text-popover-foreground',
}

const ICON_TONE: Record<ToastVariant, string> = {
  success: 'text-success-fg',
  error: 'text-error-fg',
  warning: 'text-warning-fg',
  info: 'text-info-fg',
  loading: 'text-primary',
  default: 'text-primary',
}

function VariantIcon({ record }: { record: ToastRecord }) {
  const cls = cn('size-5 shrink-0', ICON_TONE[record.variant])
  if (record.icon) return <span className={cls}>{record.icon as React.ReactNode}</span>
  switch (record.variant) {
    case 'success':
      return <CircleCheck className={cls} aria-hidden />
    case 'error':
      return <CircleX className={cls} aria-hidden />
    case 'warning':
      return <TriangleAlert className={cls} aria-hidden />
    case 'info':
      return <Info className={cls} aria-hidden />
    case 'loading':
      return <LoaderCircle className={cn(cls, 'animate-spin motion-reduce:animate-none')} aria-hidden />
    default:
      return null
  }
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const SWIPE_DISMISS_PX = 72

function ToastItem({ record }: { record: ToastRecord }) {
  const { id, variant, duration, revision, dismissed } = record
  const [paused, setPaused] = React.useState(false)
  const [leaving, setLeaving] = React.useState(false)
  const [dx, setDx] = React.useState(0)
  const drag = React.useRef<{ x: number; pointerId: number } | null>(null)
  const remaining = React.useRef(duration)
  const startedAt = React.useRef(0)

  // Restart the clock whenever the toast is updated in place.
  React.useEffect(() => {
    remaining.current = duration
  }, [duration, revision])

  // Auto-dismiss, paused while hovered, focused or being dragged.
  React.useEffect(() => {
    if (paused || dismissed || !Number.isFinite(remaining.current)) return
    startedAt.current = Date.now()
    const timer = window.setTimeout(() => toast.dismiss(id), Math.max(remaining.current, 0))
    return () => {
      window.clearTimeout(timer)
      remaining.current -= Date.now() - startedAt.current
    }
  }, [paused, dismissed, id, revision, duration])

  // Exit animation, then physical removal.
  React.useEffect(() => {
    if (!dismissed) return
    setLeaving(true)
    const timer = window.setTimeout(() => toastStore.remove(id), prefersReducedMotion() ? 0 : 160)
    return () => window.clearTimeout(timer)
  }, [dismissed, id])

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('button')) return
    drag.current = { x: e.clientX, pointerId: e.pointerId }
    e.currentTarget.setPointerCapture(e.pointerId)
    setPaused(true)
  }
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (drag.current) setDx(e.clientX - drag.current.x)
  }
  const endDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return
    const moved = e.clientX - drag.current.x
    drag.current = null
    setPaused(false)
    if (Math.abs(moved) >= SWIPE_DISMISS_PX) toast.dismiss(id)
    setDx(0)
  }

  const isError = variant === 'error'
  return (
    <div
      role={isError ? 'alert' : 'status'}
      aria-live={isError ? 'assertive' : 'polite'}
      aria-atomic="true"
      data-slot="toast"
      data-variant={variant}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => !drag.current && setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setPaused(false)
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onKeyDown={(e) => {
        if (e.key === 'Escape') toast.dismiss(id)
      }}
      style={dx ? { transform: `translateX(${dx}px)`, opacity: Math.max(0.3, 1 - Math.abs(dx) / 240) } : undefined}
      className={cn(
        'pointer-events-auto flex w-full touch-pan-y items-start gap-3 rounded-xl border py-3 pr-1 pl-4 text-sm shadow-lift select-none',
        'motion-safe:animate-in motion-safe:duration-200 motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-3',
        leaving &&
          'motion-safe:animate-out motion-safe:duration-150 motion-safe:fade-out-0 motion-safe:fill-mode-forwards',
        SURFACE[variant],
      )}
    >
      <span className="mt-0.5">
        <VariantIcon record={record} />
      </span>
      <div className="min-w-0 flex-1 py-0.5">
        <p className="font-semibold break-words">{record.title}</p>
        {record.description ? <p className="mt-0.5 break-words opacity-90">{record.description}</p> : null}
        {record.action ? (
          <button
            type="button"
            onClick={() => {
              record.action?.onClick()
              toast.dismiss(id)
            }}
            className="mt-2 inline-flex min-h-11 items-center rounded-lg border border-current px-3.5 text-sm font-semibold outline-none hover:bg-foreground/10 focus-visible:ring-[3px] focus-visible:ring-ring/60"
          >
            {record.action.label}
          </button>
        ) : null}
      </div>
      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={() => toast.dismiss(id)}
        className="-my-0.5 grid size-11 shrink-0 place-items-center rounded-lg outline-none hover:bg-foreground/10 focus-visible:ring-[3px] focus-visible:ring-ring/60"
      >
        <X className="size-4" aria-hidden />
      </button>
    </div>
  )
}

/** Only the first mounted Toaster renders, so a legacy ToastProvider and the root Toaster never double up. */
const activeToasters = new Set<string>()

/**
 * Mount once in the app root. Stacks bottom-centre on phones and bottom-right from `sm`, above the safe area.
 * Errors are announced assertively (role="alert"); everything else politely (role="status").
 */
export function Toaster({ className }: { className?: string }) {
  const id = React.useId()
  const [primary, setPrimary] = React.useState(true)
  React.useEffect(() => {
    activeToasters.add(id)
    setPrimary(activeToasters.values().next().value === id)
    return () => {
      activeToasters.delete(id)
    }
  }, [id])
  const records = React.useSyncExternalStore(toastStore.subscribe, toastStore.getSnapshot, () => [])
  if (!primary) return null
  return (
    <section
      aria-label="Notifications"
      data-slot="toaster"
      className={cn(
        'pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:items-end sm:px-6',
        className,
      )}
    >
      {records.map((record) => (
        <div key={record.id} className="w-full max-w-md sm:w-96">
          <ToastItem record={record} />
        </div>
      ))}
    </section>
  )
}

export interface ToastInput {
  message: string
  /** An optional single action, for example Undo. */
  actionLabel?: string
  onAction?: () => void
  durationMs?: number
}

/** Back-compat wrapper: renders the Toaster. Prefer mounting <Toaster /> once at the app root. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <Toaster />
    </>
  )
}

/** Back-compat: `useToast().show({ message })`. New code should call `toast.*` directly. */
export function useToast() {
  return React.useMemo(
    () => ({
      show: (input: ToastInput) =>
        toast.custom(input.message, {
          duration: input.durationMs ?? (input.actionLabel ? 10_000 : undefined),
          action: input.actionLabel ? { label: input.actionLabel, onClick: () => input.onAction?.() } : undefined,
        }),
      dismiss: (id?: string) => toast.dismiss(id),
    }),
    [],
  )
}
