import { ButtonLink, EmptyState, PageHeader, Skeleton, Sparkles } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { ForgottenTable } from '../components/ForgottenRow'
import { LoadError, RecallShell } from '../components/RecallShell'
import { useForgotten } from '../hooks/useForgotten'

function Forgotten() {
  const q = useForgotten({ limit: 30 })
  return (
    <>
      <PageHeader
        title="Slipping away"
        description="Cards you keep missing. A short review now stops them being forgotten."
        actions={
          q.data && q.data.length > 0 ? (
            <ButtonLink asChild>
              <Link to="/app/recall/review" search={{ source: 'forgotten' }}>
                Review these {q.data.length} cards
              </Link>
            </ButtonLink>
          ) : null
        }
      />
      {q.isPending ? (
        <div aria-busy="true" className="space-y-1">
          <span className="sr-only" role="status">
            Loading…
          </span>
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : q.isError ? (
        <LoadError what="your list" onRetry={() => void q.refetch()} />
      ) : q.data.length === 0 ? (
        <EmptyState
          className="rounded-lg py-6"
          icon={<Sparkles aria-hidden />}
          title="Nothing is slipping away"
          description="No card has been missed repeatedly lately. Keep going."
        />
      ) : (
        <ForgottenTable items={q.data} />
      )}
    </>
  )
}

export function ForgottenContainer() {
  return (
    <RecallShell>
      <Forgotten />
    </RecallShell>
  )
}
