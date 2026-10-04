import { Alert, Skeleton } from '@artha/design-system'

import { DueList } from '../components/DueList'
import { useDue } from '../hooks/useCoverageQueries'
import { CoverageShell } from './CoverageShell'

function Body() {
  const { data, isPending, isError } = useDue()
  return (
    <>
      <header className="space-y-2">
        <h1 className="font-display text-3xl font-extrabold">Due for revision</h1>
        <p className="text-muted-foreground">
          Chapters whose revision date has arrived. The most overdue and highest-marks chapters come first.
        </p>
      </header>
      {isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : isError || !data ? (
        <Alert variant="error">We could not load your revisions.</Alert>
      ) : (
        <DueList rows={data.results} />
      )}
    </>
  )
}

export function RevisionContainer() {
  return <CoverageShell>{() => <Body />}</CoverageShell>
}
