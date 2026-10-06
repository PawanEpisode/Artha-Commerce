import type { ReactNode, Ref } from 'react'

/**
 * The frame every branch of the alerts step shares: one card with its own `h2` (the step's `h1` belongs to the flow).
 * The heading takes focus when the branch changes, so a keyboard or screen reader user never lands on nothing.
 */
export function AlertsCard({
  id,
  title,
  badge,
  headingRef,
  children,
}: {
  id: string
  title: string
  badge?: ReactNode
  headingRef?: Ref<HTMLHeadingElement>
  children: ReactNode
}) {
  return (
    <section aria-labelledby={id} className="space-y-4 rounded-2xl border border-border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={id} ref={headingRef} tabIndex={-1} className="text-lg font-bold outline-none">
          {title}
        </h2>
        {badge}
      </div>
      {children}
    </section>
  )
}

/** Buttons sit in one wrapping row; a long label wraps instead of overflowing at 320 px. */
export const AlertsActions = ({ children }: { children: ReactNode }) => (
  <div className="flex flex-wrap items-center gap-3">{children}</div>
)

/** Shown when saving the student's choice failed: said once, in words, with the retry being the same button. */
export const SAVE_FAILED = 'We could not save that. Check your connection and press the button again.'
