import { Alert } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { Backlog } from '../lib/types'

/** Backlog the day cannot hold ("38 revisions are overdue, 3 are scheduled today"), each with its link. Never blocks the list. */
export function OverloadNotice({ backlog }: { backlog: Backlog[] }) {
  if (!backlog.length) return null
  return (
    <Alert variant="info">
      <ul className="space-y-1">
        {backlog.map((b) => (
          <li key={b.kind}>
            {b.link ? (
              <Link
                to={b.link.path as never}
                search={b.link.search as never}
                className="font-medium underline underline-offset-4"
              >
                {b.label}
              </Link>
            ) : (
              b.label
            )}
          </li>
        ))}
      </ul>
    </Alert>
  )
}
