import {
  Alert,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  ProgressBar,
  Skeleton,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { ChapterList } from '../components/ChapterList'
import { useOverview, useSubjectCoverage } from '../hooks/useCoverageQueries'
import { pick } from '../lib/formula'
import { CoverageShell } from './CoverageShell'

function SubjectBody({ subjectId }: { subjectId: string }) {
  const { data, isPending, isError } = useSubjectCoverage(subjectId)
  const overview = useOverview().data
  const weighted = overview?.weighted_default ?? false

  if (isPending) return <Skeleton className="h-64 w-full" />
  if (isError || !data) return <Alert variant="error">This paper is not part of your syllabus.</Alert>

  const pct = pick(data.subject, weighted)
  return (
    <>
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <Link to="/app/syllabus" className="underline-offset-4 hover:underline">
              Syllabus map
            </Link>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{data.subject.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <header className="space-y-3">
        <h1 className="font-display text-3xl font-extrabold">{data.subject.name}</h1>
        <p className="text-muted-foreground">
          {pct}% covered. {data.subject.chapters_done} of {data.subject.chapters_total} chapters done.
        </p>
        <ProgressBar size="lg" value={pct} label={`${data.subject.name} coverage`} />
      </header>
      {data.chapters.length === 0 ? (
        <p className="rounded-xl border border-dashed p-6 text-muted-foreground">
          Chapters for this paper are coming soon.
        </p>
      ) : (
        <ChapterList subjectId={data.subject.id} chapters={data.chapters} />
      )}
    </>
  )
}

export function SubjectContainer({ subjectId }: { subjectId: string }) {
  return <CoverageShell>{() => <SubjectBody subjectId={subjectId} />}</CoverageShell>
}
