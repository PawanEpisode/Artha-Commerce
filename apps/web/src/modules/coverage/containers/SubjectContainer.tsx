import {
  Alert,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  EntityBadge,
  Label,
  ProgressBar,
  Skeleton,
  Switch,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'

import { EntityCrumb, ReportIssue } from '~/modules/syllabus'

import { ChapterList } from '../components/ChapterList'
import { useOverview, useSubjectCoverage } from '../hooks/useCoverageQueries'
import { pick } from '../lib/formula'
import { paperSentence } from '../lib/progress'
import { CoverageShell } from './CoverageShell'

export interface SubjectSearch {
  view?: 'weighted' | 'simple'
}

function SubjectBody({ subjectId, search }: { subjectId: string; search: SubjectSearch }) {
  const navigate = useNavigate({ from: '/app/syllabus/$subject/' })
  const { data, isPending, isError } = useSubjectCoverage(subjectId)
  const overview = useOverview().data
  // Same rule as the map: an explicit ?view wins, otherwise the student's saved default.
  const weighted = search.view ? search.view === 'weighted' : (overview?.weighted_default ?? false)

  if (isPending) return <Skeleton className="h-64 w-full" />
  if (isError || !data) return <Alert variant="error">This paper is not part of your syllabus.</Alert>

  const pct = pick(data.subject, weighted)
  return (
    <>
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <Link
              to="/app/syllabus"
              search={search.view ? { view: search.view } : {}}
              className="underline-offset-4 hover:underline"
            >
              Syllabus map
            </Link>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>
              <EntityCrumb kind="paper">{data.subject.name}</EntityCrumb>
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <header className="space-y-3">
        <EntityBadge kind="paper" size="lg">
          {data.subject.paper_number ? `Paper ${data.subject.paper_number}` : 'Paper'}
        </EntityBadge>
        <h1 className="font-display text-3xl font-extrabold break-words">{data.subject.name}</h1>
        <p className="text-muted-foreground">
          {paperSentence(pct, {
            chaptersDone: data.subject.chapters_done,
            chaptersStarted: data.subject.chapters_started,
            chaptersTotal: data.subject.chapters_total,
          })}
        </p>
        <ProgressBar size="lg" value={pct} label={`${data.subject.name} coverage`} />
        <div className="flex items-center gap-2">
          <Switch
            id="subject-weighted-view"
            checked={weighted}
            onCheckedChange={(w) =>
              void navigate({ search: (prev) => ({ ...prev, view: w ? 'weighted' : 'simple' }), replace: true })
            }
          />
          <Label htmlFor="subject-weighted-view">Weight by marks</Label>
        </div>
      </header>
      {data.chapters.length === 0 ? (
        <p className="rounded-xl border border-dashed p-6 text-muted-foreground">
          Chapters for this paper are coming soon.
        </p>
      ) : (
        <ChapterList subjectId={data.subject.id} chapters={data.chapters} />
      )}
      <ReportIssue nodeType="subject" nodeId={data.subject.id} />
    </>
  )
}

export function SubjectContainer({ subjectId, search = {} }: { subjectId: string; search?: SubjectSearch }) {
  return <CoverageShell>{() => <SubjectBody subjectId={subjectId} search={search} />}</CoverageShell>
}
