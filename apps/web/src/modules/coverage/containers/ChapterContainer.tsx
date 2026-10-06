import {
  Alert,
  ArrowLeft,
  ArrowRight,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  Button,
  Card,
  ConfidenceDot,
  EntityBadge,
  EntityDot,
  Label,
  ProgressRing,
  Skeleton,
  Switch,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { coverageBucket, track } from '~/modules/observability'
import { CRUMB_LINK_CLASS, EntityCrumb, ReportIssue } from '~/modules/syllabus'

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
import { chapterActivities, confidenceAllowed } from '../lib/rules'
import { CoverageShell } from './CoverageShell'

const date = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : null

function ChapterBody({ subjectId, chapterId }: { subjectId: string; chapterId: string }) {
  const { data, isPending, isError } = useChapterCoverage(chapterId)
  const { data: settings } = useCoverageSettings()
  const ctx = {
    chapterId,
    subjectId,
    subjectKey: data?.subject.key ?? '',
    chapterKey: data?.chapter.key ?? '',
    chapterName: data?.chapter.name,
  }
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
            <Link to="/app/syllabus/$subject" params={{ subject: subject.id }} className={CRUMB_LINK_CLASS}>
              <EntityCrumb kind="paper">{subject.name}</EntityCrumb>
            </Link>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>
              <EntityCrumb kind="chapter">{chapter.name}</EntityCrumb>
            </BreadcrumbPage>
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
          <EntityBadge kind="chapter">Chapter</EntityBadge>
          <h1 className="font-display text-2xl font-extrabold break-words sm:text-3xl">{chapter.name}</h1>
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
        <nav aria-label="Chapters in this paper" className="grid gap-3 sm:grid-cols-2">
          {data.prev_chapter ? (
            <Button
              variant="outline"
              className="h-auto min-h-11 justify-start py-2 text-left whitespace-normal"
              asChild
            >
              <Link
                to="/app/syllabus/$subject/$chapter"
                params={{ subject: subject.id, chapter: data.prev_chapter.id }}
                title={data.prev_chapter.name}
              >
                <ArrowLeft aria-hidden />
                <span className="min-w-0">
                  <span className="block text-xs font-medium text-muted-foreground">Previous chapter</span>
                  <span className="line-clamp-2 break-words">{data.prev_chapter.name}</span>
                </span>
              </Link>
            </Button>
          ) : (
            <span />
          )}
          {data.next_chapter ? (
            <Button variant="outline" className="h-auto min-h-11 justify-end py-2 text-right whitespace-normal" asChild>
              <Link
                to="/app/syllabus/$subject/$chapter"
                params={{ subject: subject.id, chapter: data.next_chapter.id }}
                title={data.next_chapter.name}
              >
                <span className="min-w-0">
                  <span className="block text-xs font-medium text-muted-foreground">Next chapter</span>
                  <span className="line-clamp-2 break-words">{data.next_chapter.name}</span>
                </span>
                <ArrowRight aria-hidden />
              </Link>
            </Button>
          ) : null}
        </nav>
      ) : null}

      <section aria-labelledby="topics-h" className="space-y-3">
        <h2 id="topics-h" className="flex items-center gap-2.5 font-display text-xl font-bold">
          <EntityDot kind="topic" />
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
            activities={chapterActivities(chapter)}
            pending={log.isPending}
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
          onLockedShown={() => track('confidence_blocked', { coverage_bucket: coverageBucket(chapter.coverage_pct) })}
          value={chapter.confidence}
          coveragePct={chapter.coverage_pct}
          unlocked={confidenceAllowed(chapter.coverage_pct)}
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
