import { ButtonLink, EmptyState, Skeleton, Sparkles } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { ForgottenRow } from '../components/ForgottenRow'
import { LoadError, RecallShell } from '../components/RecallShell'
import { useForgotten } from '../hooks/useForgotten'

function Forgotten() {
  const q = useForgotten({ limit: 30 })
  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Slipping away</h1>
        <p className="text-muted-foreground">Cards you keep missing. A short review now stops them being forgotten.</p>
      </header>
      {q.isPending ? (
        <div aria-busy="true" className="space-y-3">
          <span className="sr-only" role="status">
            Loading…
          </span>
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : q.isError ? (
        <LoadError what="your list" onRetry={() => void q.refetch()} />
      ) : q.data.length === 0 ? (
        <EmptyState
          icon={<Sparkles aria-hidden />}
          title="Nothing is slipping away"
          description="No card has been missed repeatedly lately. Keep going."
        />
      ) : (
        <>
          <ButtonLink size="lg" asChild>
            <Link to="/app/recall/review" search={{ source: 'forgotten' }}>
              Review these {q.data.length} cards
            </Link>
          </ButtonLink>
          <ul className="space-y-3">
            {q.data.map((f) => (
              <ForgottenRow key={f.card_id} item={f} />
            ))}
          </ul>
        </>
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
