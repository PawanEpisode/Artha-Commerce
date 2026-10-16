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
  EntityDot,
  Label,
  PageHeader,
  ProgressBar,
  Skeleton,
  Switch,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

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

/** What another module needs to put its own section on the chapter page (stable keys, never ids). */
export interface ChapterSlotContext {
  subjectKey: string
  chapterKey: string
  chapterName: string
}

function ChapterBody({
  subjectId,
  chapterId,
  renderNotes,
}: {
  subjectId: string
  chapterId: string
  renderNotes?: (context: ChapterSlotContext) => ReactNode
}) {
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

  if (isPending) return <Skeleton className="h-64 w-full" />
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

      <PageHeader
        eyebrow="Chapter"
        title={<span className="line-clamp-2 break-words whitespace-normal">{chapter.name}</span>}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge status={chapter.status} />
            {chapter.confidence ? <ConfidenceDot value={chapter.confidence} showLabel /> : null}
            <span className="tabular-nums">
              {chapter.is_excluded ? 'Left out' : `${chapter.coverage_pct}% covered`}
            </span>
            <CalculationPopover weights={weights} />
          </span>
        }
        actions={
          data.prev_chapter || data.next_chapter ? (
            <nav aria-label="Chapters in this paper" className="flex flex-wrap gap-2">
              {data.prev_chapter ? (
                <Button variant="outline" size="sm" className="max-w-56" asChild>
                  <Link
                    to="/app/syllabus/$subject/$chapter"
                    params={{ subject: subject.id, chapter: data.prev_chapter.id }}
                    title={data.prev_chapter.name}
                  >
                    <ArrowLeft aria-hidden />
                    <span className="min-w-0 truncate">
                      <span className="sr-only">Previous chapter: </span>
                      {data.prev_chapter.name}
                    </span>
                  </Link>
                </Button>
              ) : null}
              {data.next_chapter ? (
                <Button variant="outline" size="sm" className="max-w-56" asChild>
                  <Link
                    to="/app/syllabus/$subject/$chapter"
                    params={{ subject: subject.id, chapter: data.next_chapter.id }}
                    title={data.next_chapter.name}
                  >
                    <span className="min-w-0 truncate">
                      <span className="sr-only">Next chapter: </span>
                      {data.next_chapter.name}
                    </span>
                    <ArrowRight aria-hidden />
                  </Link>
                </Button>
              ) : null}
            </nav>
          ) : undefined
        }
      />
      <p role="status" className="sr-only">
        {chapter.name} is {chapter.coverage_pct} percent covered.
      </p>

      <div className="grid items-start gap-x-6 gap-y-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-4">
          <section aria-labelledby="topics-h" className="space-y-2">
            <h2 id="topics-h" className="flex items-center gap-2 text-sm font-semibold">
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

          {renderNotes
            ? renderNotes({ subjectKey: subject.key, chapterKey: chapter.key, chapterName: chapter.name })
            : null}

          <section aria-labelledby="log-h" className="space-y-2">
            <h2 id="log-h" className="text-sm font-semibold">
              Log your work
            </h2>
            <Card className="p-4">
              <LogActions
                activities={chapterActivities(chapter)}
                pending={log.isPending}
                onLog={(type, value) => log.mutate({ type, value })}
              />
            </Card>
            {nextDue ? <p className="text-xs text-muted-foreground">Next revision due {nextDue}.</p> : null}
            {lastStudied ? (
              <p className="text-xs text-muted-foreground">
                Last studied {lastStudied}
                {minutes > 0 ? `, ${minutes} minutes in total.` : '.'}
              </p>
            ) : null}
            <ActivityLog events={data.events} />
          </section>
        </div>

        <aside
          aria-label="Chapter progress"
          className="min-w-0 space-y-4 xl:sticky xl:top-[calc(var(--site-header-height,2.75rem)+1rem)]"
        >
          <Card className="space-y-3 p-4">
            <h2 className="text-sm font-semibold">What makes up the percent</h2>
            <ProgressBar
              size="lg"
              value={chapter.is_excluded ? 0 : chapter.coverage_pct}
              label={`${chapter.name} coverage`}
            />
            <ComponentBreakdown chapter={chapter} weights={weights} />
          </Card>

          <section aria-labelledby="conf-h" className="space-y-2">
            <h2 id="conf-h" className="text-sm font-semibold">
              How confident do you feel?
            </h2>
            <ConfidencePicker
              onLockedShown={() =>
                track('confidence_blocked', { coverage_bucket: coverageBucket(chapter.coverage_pct) })
              }
              value={chapter.confidence}
              coveragePct={chapter.coverage_pct}
              unlocked={confidenceAllowed(chapter.coverage_pct)}
              disabled={confidence.isPending}
              onChange={(v) => confidence.mutate(v)}
            />
          </section>

          <Card className="flex items-center justify-between gap-4 p-4">
            <div className="min-w-0">
              <Label htmlFor="exclude-chapter" className="text-[13px] font-semibold">
                Leave this chapter out
              </Label>
              <p className="mt-0.5 text-xs text-muted-foreground">
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

          <ReportIssue nodeType="chapter" nodeId={chapter.id} />
        </aside>
      </div>
    </>
  )
}

export function ChapterContainer({
  subjectId,
  chapterId,
  renderNotes,
}: {
  subjectId: string
  chapterId: string
  /** A slot after the topics, for the notes section. Kept as a render prop so coverage never imports notes. */
  renderNotes?: (context: ChapterSlotContext) => ReactNode
}) {
  return (
    <CoverageShell>
      {() => <ChapterBody subjectId={subjectId} chapterId={chapterId} renderNotes={renderNotes} />}
    </CoverageShell>
  )
}
