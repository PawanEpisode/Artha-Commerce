import {
  Alert,
  ArrowLeft,
  ArrowRight,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  Card,
  ConfidenceDot,
  Label,
  ProgressRing,
  Skeleton,
  Switch,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { ReportIssue } from '~/modules/syllabus'

import { CalculationPopover } from '../components/CalculationPopover'
import { ComponentBreakdown } from '../components/ComponentBreakdown'
import { ConfidencePicker } from '../components/ConfidencePicker'
import { LogActions } from '../components/LogActions'
import { ActivityLog } from '../components/RevisionHistory'
import { StatusBadge } from '../components/StatusBadge'
import { TopicChecklist } from '../components/TopicChecklist'
import { useLogEvent, useSetChapterExclusion, useSetConfidence, useTickTopic } from '../hooks/useChapterMutations'
import { useChapterCoverage, useCoverageSettings } from '../hooks/useCoverageQueries'
import { DEFAULT_WEIGHTS } from '../lib/formula'
import { CoverageShell } from './CoverageShell'

const date = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : null

function ChapterBody({ subjectId, chapterId }: { subjectId: string; chapterId: string }) {
  const { data, isPending, isError } = useChapterCoverage(chapterId)
  const { data: settings } = useCoverageSettings()
  const ctx = { chapterId, subjectId, subjectKey: data?.subject.key ?? '', chapterKey: data?.chapter.key ?? '' }
  const tick = useTickTopic(ctx)
  const log = useLogEvent(ctx)
  const confidence = useSetConfidence(ctx)
  const exclusion = useSetChapterExclusion(ctx)

  if (isPending) return <Skeleton className="h-80 w-full" />
  if (isError || !data) return <Alert variant="error">This chapter is not part of your syllabus.</Alert>

  const { chapter, subject } = data
  const weights = settings
    ? { w_read: settings.w_read, w_practice: settings.w_practice, w_revise: settings.w_revise, w_mock: settings.w_mock }
    : {
        w_read: DEFAULT_WEIGHTS.read,
        w_practice: DEFAULT_WEIGHTS.practice,
        w_revise: DEFAULT_WEIGHTS.revise,
        w_mock: DEFAULT_WEIGHTS.mock,
      }
  const minutes = Math.round(chapter.total_study_seconds / 60)
  const lastStudied = date(chapter.last_studied_at)
  const nextDue = date(chapter.next_revision_due)

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
            <Link
              to="/app/syllabus/$subject"
              params={{ subject: subject.id }}
              className="underline-offset-4 hover:underline"
            >
              {subject.name}
            </Link>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{chapter.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <header className="flex items-center gap-5">
        <ProgressRing
          value={chapter.is_excluded ? 0 : chapter.coverage_pct}
          label={`${chapter.name} coverage`}
          size={96}
          strokeWidth={9}
        />
        <div className="min-w-0 space-y-2">
          <h1 className="font-display text-2xl font-extrabold sm:text-3xl">{chapter.name}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={chapter.status} />
            {chapter.confidence ? <ConfidenceDot value={chapter.confidence} showLabel /> : null}
          </div>
          <CalculationPopover weights={weights} />
        </div>
      </header>
      <p role="status" className="sr-only">
        {chapter.name} is {chapter.coverage_pct} percent covered.
      </p>

      {data.prev_chapter || data.next_chapter ? (
        <nav aria-label="Chapters in this paper" className="flex justify-between gap-3 text-sm">
          {data.prev_chapter ? (
            <Link
              to="/app/syllabus/$subject/$chapter"
              params={{ subject: subject.id, chapter: data.prev_chapter.id }}
              className="inline-flex min-h-11 items-center gap-2 font-medium underline-offset-4 hover:underline"
            >
              <ArrowLeft aria-hidden className="size-4" />
              {data.prev_chapter.name}
            </Link>
          ) : (
            <span />
          )}
          {data.next_chapter ? (
            <Link
              to="/app/syllabus/$subject/$chapter"
              params={{ subject: subject.id, chapter: data.next_chapter.id }}
              className="inline-flex min-h-11 items-center gap-2 font-medium underline-offset-4 hover:underline"
            >
              {data.next_chapter.name}
              <ArrowRight aria-hidden className="size-4" />
            </Link>
          ) : null}
        </nav>
      ) : null}

      <section aria-labelledby="topics-h" className="space-y-3">
        <h2 id="topics-h" className="font-display text-xl font-bold">
          Topics
        </h2>
        <TopicChecklist
          topics={data.topics}
          chapterName={chapter.name}
          hasTopics={chapter.has_topics}
          chapterDone={chapter.topics_done > 0}
          onToggleTopic={(topicId, done) => tick.mutate({ topicId, done })}
          onToggleChapter={(done) => tick.mutate({ topicId: null, done })}
        />
        {tick.isError ? <Alert variant="error">We could not save that tick. It has been put back.</Alert> : null}
      </section>

      <Card className="space-y-4 p-6">
        <h2 className="font-display text-xl font-bold">What makes up the percent</h2>
        <ComponentBreakdown chapter={chapter} weights={weights} />
      </Card>

      <section aria-labelledby="log-h" className="space-y-3">
        <h2 id="log-h" className="font-display text-xl font-bold">
          Log your work
        </h2>
        <Card className="p-6">
          <LogActions
            pending={log.isPending}
            error={log.isError ? 'We could not save that. Please try again.' : undefined}
            onLog={(type, value) => log.mutate({ type, value })}
          />
        </Card>
        {nextDue ? <p className="text-sm text-muted-foreground">Next revision due {nextDue}.</p> : null}
        {lastStudied ? (
          <p className="text-sm text-muted-foreground">
            Last studied {lastStudied}
            {minutes > 0 ? `, ${minutes} minutes in total.` : '.'}
          </p>
        ) : null}
        <ActivityLog events={data.events} />
      </section>

      <section aria-labelledby="conf-h" className="space-y-3">
        <h2 id="conf-h" className="font-display text-xl font-bold">
          How confident do you feel?
        </h2>
        <ConfidencePicker
          value={chapter.confidence}
          disabled={confidence.isPending}
          onChange={(v) => confidence.mutate(v)}
        />
      </section>

      <Card className="flex items-center justify-between gap-4 p-6">
        <div>
          <Label htmlFor="exclude-chapter" className="text-base font-semibold">
            Leave this chapter out
          </Label>
          <p className="mt-1 text-sm text-muted-foreground">
            Excluded chapters are not counted in your percentages. Your progress is kept.
          </p>
        </div>
        <Switch
          id="exclude-chapter"
          checked={chapter.is_excluded}
          disabled={exclusion.isPending}
          onCheckedChange={(v) => exclusion.mutate(v)}
        />
      </Card>

      <div>
        <ReportIssue nodeType="chapter" nodeId={chapter.id} />
      </div>
    </>
  )
}

export function ChapterContainer({ subjectId, chapterId }: { subjectId: string; chapterId: string }) {
  return <CoverageShell>{() => <ChapterBody subjectId={subjectId} chapterId={chapterId} />}</CoverageShell>
}
