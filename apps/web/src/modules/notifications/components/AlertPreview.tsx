import { Bell } from '@artha/design-system'

/** A made-up example of the alert, so the student sees what they are agreeing to. Text, not a screenshot. */
export function AlertPreview() {
  return (
    <figure className="m-0 space-y-2">
      <div className="flex items-start gap-3 rounded-xl border border-border bg-secondary p-4">
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Bell aria-hidden className="size-4" />
        </span>
        <div className="min-w-0 text-sm">
          <p className="font-semibold text-foreground">Round 2 done</p>
          <p className="text-muted-foreground">25 minutes on Direct Tax. Take 5, you earned it.</p>
        </div>
      </div>
      <figcaption className="text-xs text-muted-foreground">
        An example of an alert on your phone or desktop.
      </figcaption>
    </figure>
  )
}
