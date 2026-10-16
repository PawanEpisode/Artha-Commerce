import { Alert, PageHeader, Skeleton } from '@artha/design-system'

import { DueList, type DueRowAction } from '../components/DueList'
import { useDue } from '../hooks/useCoverageQueries'
import { CoverageShell } from './CoverageShell'

function Body({ renderRowAction }: { renderRowAction?: DueRowAction }) {
  const { data, isPending, isError } = useDue()
  return (
    <>
      <PageHeader
        title="Due for revision"
        description="Chapters whose revision date has arrived. The most overdue and highest-marks chapters come first."
      />
      {isPending ? (
        <div className="space-y-1.5">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : isError || !data ? (
        <Alert variant="error">We could not load your revisions.</Alert>
      ) : (
        <DueList rows={data.results} renderAction={renderRowAction} />
      )}
    </>
  )
}

export function RevisionContainer({ renderRowAction }: { renderRowAction?: DueRowAction }) {
  return <CoverageShell>{() => <Body renderRowAction={renderRowAction} />}</CoverageShell>
}
