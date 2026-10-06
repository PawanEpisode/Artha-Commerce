import { Button, Label, SelectField, type SelectOption } from '@artha/design-system'

/** Time zone picker with the browser's own zone offered when it differs from the saved one. */
export function TimeZoneField({
  value,
  options,
  proposal,
  onChange,
}: {
  value: string
  options: readonly SelectOption[]
  /** The browser's zone when it differs from `value`, else null. */
  proposal: string | null
  onChange: (zone: string) => void
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor="notification-timezone">Your time zone</Label>
      <SelectField id="notification-timezone" value={value} onValueChange={onChange} options={options} />
      <p className="text-sm text-muted-foreground">Quiet hours and the daily nudge follow this time zone.</p>
      {proposal ? (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-input bg-secondary p-3 text-sm">
          <span className="min-w-0 flex-1">
            Your browser says you are in <strong>{proposal.replace(/_/g, ' ')}</strong>.
          </span>
          <Button type="button" variant="outline" size="sm" onClick={() => onChange(proposal)}>
            Use this time zone
          </Button>
        </div>
      ) : null}
    </div>
  )
}
