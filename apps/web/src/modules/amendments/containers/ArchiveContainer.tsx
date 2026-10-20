import { Alert, ArrowRight, Badge, Button, Card, EmptyState, History, Skeleton } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useMyArchive } from '../hooks/useMyArchive'
import { AmendmentsShell } from './AmendmentsShell'

export function ArchiveContainer() {
  const { data: terms, isPending, isError, refetch } = useMyArchive()

  return (
    <AmendmentsShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">Term Archive</h1>
          <p className="text-sm text-muted-foreground">
            Explore past statutory and academic amendment packages by examination attempt.
          </p>
        </div>

        {isPending ? (
          <div aria-busy="true" className="space-y-3">
            <span className="sr-only" role="status">
              Loading term archive…
            </span>
            <Skeleton className="h-20 w-full rounded-lg" />
            <Skeleton className="h-20 w-full rounded-lg" />
            <Skeleton className="h-20 w-full rounded-lg" />
          </div>
        ) : isError ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center justify-between gap-3">
              <span>Could not load amendment archive.</span>
              <Button size="sm" variant="outline" onClick={() => void refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : !terms || terms.length === 0 ? (
          <EmptyState
            className="rounded-lg border border-dashed py-12"
            icon={<History className="h-10 w-10 text-muted-foreground" aria-hidden />}
            title="No past terms archived"
            description="Historical terms will appear here once new exam cycles take effect."
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {terms.map((term) => (
              <Card key={term.term_code} className="flex flex-col justify-between p-5">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold tracking-wide text-primary uppercase">{term.term_code}</span>
                    <Badge variant={term.applicability === 'applies' ? 'accent' : 'outline'} className="text-xs">
                      {term.applicability === 'applies' ? 'Your Attempt' : 'Past Term'}
                    </Badge>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-2 text-center">
                    <div className="rounded-md bg-muted/40 p-2.5">
                      <div className="text-xl font-bold text-foreground">{term.documents_count}</div>
                      <div className="text-xs text-muted-foreground">Documents</div>
                    </div>
                    <div className="rounded-md bg-muted/40 p-2.5">
                      <div className="text-xl font-bold text-foreground">{term.cards_count}</div>
                      <div className="text-xs text-muted-foreground">Change Cards</div>
                    </div>
                  </div>
                </div>

                <div className="mt-5 border-t pt-3">
                  <Link
                    to="/app/amendments"
                    search={{ term: term.term_code }}
                    className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border py-2 text-xs font-medium text-foreground hover:bg-muted"
                  >
                    View Term Amendments
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AmendmentsShell>
  )
}
