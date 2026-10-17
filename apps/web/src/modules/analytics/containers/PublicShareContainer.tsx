import { Alert, Badge, Page, PageHeader, Skeleton } from '@artha/design-system'

import { OverviewCards } from '../components/OverviewCards'
import { ReadinessCard } from '../components/ReadinessCard'
import { usePublicShare } from '../hooks/useAnalytics'

interface PublicShareContainerProps {
  token: string
}

export function PublicShareContainer({ token }: PublicShareContainerProps) {
  const { data, isLoading, error } = usePublicShare(token)

  if (isLoading) {
    return (
      <Page width="fluid">
        <div className="space-y-6 py-8">
          <Skeleton className="h-10 w-1/3" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      </Page>
    )
  }

  if (error || !data) {
    return (
      <Page width="form">
        <div className="space-y-4 py-12">
          <Alert variant="error">
            This progress report link has expired or is invalid. Please request a new share link from the student.
          </Alert>
        </div>
      </Page>
    )
  }

  return (
    <Page width="fluid">
      <div className="space-y-6 py-6">
        <PageHeader
          title={data.student_name ? `${data.student_name}’s Study Report` : 'Student Progress Report'}
          description={`Verified progress report for ${data.period_kind.toUpperCase()} snapshot (${data.from_date} to ${data.to_date}).`}
          actions={<Badge variant="accent">Snapshot from {new Date(data.created_at).toLocaleDateString()}</Badge>}
        />

        <OverviewCards data={data.overview} />

        <ReadinessCard data={data.readiness} />
      </div>
    </Page>
  )
}
