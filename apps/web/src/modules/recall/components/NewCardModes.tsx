import { ButtonLink } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import type { NewCardSearch } from '../lib/cardSearch'

/** "One card" or "Import many": two links, so each way of adding cards has its own URL and the keyboard path is plain tabbing. */
export function NewCardModes({ search, extra }: { search: NewCardSearch; extra?: ReactNode }) {
  const importing = search.mode === 'import'
  return (
    <nav aria-label="How to add cards" className="flex flex-wrap gap-2">
      <ButtonLink variant={importing ? 'outline' : 'default'} asChild>
        <Link
          to="/app/recall/cards/new"
          search={{ ...search, mode: undefined }}
          aria-current={importing ? undefined : 'page'}
        >
          One card
        </Link>
      </ButtonLink>
      <ButtonLink variant={importing ? 'default' : 'outline'} asChild>
        <Link
          to="/app/recall/cards/new"
          search={{ ...search, mode: 'import' }}
          aria-current={importing ? 'page' : undefined}
        >
          Import many
        </Link>
      </ButtonLink>
      {extra}
    </nav>
  )
}
