import { Link } from '@tanstack/react-router'

import type { TargetRow } from '../lib/targetsSummary'

interface Props {
  heading: string
  rows: TargetRow[]
  confirmed: boolean
}

/** What the student aims to finish in every chapter, with the way to change it. */
export function TargetsView({ heading, rows, confirmed }: Props) {
  return (
    <>
      <p className="text-[13px] text-muted-foreground">
        {confirmed
          ? `${heading}. Every chapter counts toward these.`
          : 'You have not chosen your targets yet. The standard ones are in use.'}
      </p>
      <ul className="grid grid-cols-3 gap-2">
        {rows.map((row) => (
          <li key={row.label} className="rounded-md bg-muted/50 p-2 text-center">
            <p className="text-lg font-semibold tabular-nums">{row.count ?? 'Off'}</p>
            <p className="text-xs text-muted-foreground">
              {row.count === null ? `${row.label} not tracked` : row.label}
            </p>
          </li>
        ))}
      </ul>
      <Link
        to="/app/settings/coverage"
        className="mt-auto text-[13px] font-medium text-primary underline-offset-4 hover:underline"
      >
        {confirmed ? 'Change targets' : 'Choose targets'}
      </Link>
    </>
  )
}
