import * as React from 'react'

import { X } from '../../icons'
import { cn } from '../../lib/utils'
import { Button } from './button'

export interface ToastInput {
  message: string
  /** An optional single action, for example Undo. */
  actionLabel?: string
  onAction?: () => void
  /** Milliseconds before it goes away. Default 10 s: long enough to read it and press the action. */
  durationMs?: number
}

interface ToastItem extends ToastInput {
  id: number
}

const ToastContext = React.createContext<{ show: (toast: ToastInput) => number; dismiss: (id: number) => void } | null>(
  null,
)

/** Mount once near the top of a screen. Messages are announced politely; none of them traps focus. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<ToastItem[]>([])
  const next = React.useRef(1)
  const dismiss = React.useCallback((id: number) => setItems((all) => all.filter((t) => t.id !== id)), [])
  const show = React.useCallback(
    (toast: ToastInput) => {
      const id = next.current++
      setItems((all) => [...all.slice(-2), { ...toast, id }])
      window.setTimeout(() => dismiss(id), toast.durationMs ?? 10_000)
      return id
    },
    [dismiss],
  )
  const value = React.useMemo(() => ({ show, dismiss }), [show, dismiss])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        role="region"
        aria-label="Notifications"
        className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4"
      >
        {items.map((t) => (
          <div
            key={t.id}
            role="status"
            data-slot="toast"
            className={cn(
              'pointer-events-auto flex w-full max-w-md items-center gap-3 rounded-xl border border-border bg-popover p-3 pl-4 text-sm text-popover-foreground shadow-(--shadow-lift)',
            )}
          >
            <span className="flex-1">{t.message}</span>
            {t.actionLabel ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  t.onAction?.()
                  dismiss(t.id)
                }}
              >
                {t.actionLabel}
              </Button>
            ) : null}
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => dismiss(t.id)}
              className="grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = React.useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
