import { ProgressBar } from '@artha/design-system'

/** Inline progress for a table cell: a thin bar and the percent as text, so the number is never colour only. */
export function ProgressCell({ value, label, na }: { value: number; label: string; na?: boolean }) {
  return (
    <div className="flex items-center justify-end gap-2">
      {na ? null : <ProgressBar size="sm" value={value} label={label} className="w-16 sm:w-28" />}
      <span className="w-9 text-right text-xs font-medium tabular-nums">{na ? 'n/a' : `${value}%`}</span>
    </div>
  )
}
