import { Button, Card, ChevronRight } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'

import { ReportIssue } from '~/modules/syllabus'

import { CalculationPopover } from '../components/CalculationPopover'
import { DueList } from '../components/DueList'
import { ElectivePicker } from '../components/ElectivePicker'
import { OverallRing } from '../components/OverallRing'
import { SubjectProgressList } from '../components/SubjectProgressList'
import { useSetElectives } from '../hooks/useCoverageMutations'
import { useCoverageSettings, useDue } from '../hooks/useCoverageQueries'
import { DEFAULT_WEIGHTS, pick } from '../lib/formula'
import type { Overview } from '../lib/types'
import { CoverageShell } from './CoverageShell'

export interface MapSearch {
  view?: 'weighted' | 'simple'
  status?: 'due'
}

function Map({ overview, search }: { overview: Overview; search: MapSearch }) {
  const navigate = useNavigate({ from: '/app/syllabus/' })
  const { data: settings } = useCoverageSettings()
  const due = useDue()
  const setElectives = useSetElectives()
  const weighted = search.view ? search.view === 'weighted' : overview.weighted_default
  const weights = settings
    ? { w_read: settings.w_read, w_practice: settings.w_practice, w_revise: settings.w_revise, w_mock: settings.w_mock }
    : {
        w_read: DEFAULT_WEIGHTS.read,
        w_practice: DEFAULT_WEIGHTS.practice,
        w_revise: DEFAULT_WEIGHTS.revise,
        w_mock: DEFAULT_WEIGHTS.mock,
      }

  return (
    <>
      <OverallRing
        enrollment={overview.enrollment}
        percent={pick(overview.level, weighted)}
        chaptersDone={overview.level.chapters_done}
        chaptersTotal={overview.level.chapters_total}
        weighted={weighted}
        onWeightedChange={(w) =>
          void navigate({ search: (prev) => ({ ...prev, view: w ? 'weighted' : 'simple' }), replace: true })
        }
        calculation={<CalculationPopover weights={weights} />}
      />

      {search.status === 'due' ? (
        <section aria-labelledby="due-heading" className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 id="due-heading" className="font-display text-xl font-bold">
              Due for revision
            </h2>
            <Button variant="link" asChild>
              <Link to="/app/syllabus" search={(prev) => ({ ...prev, status: undefined })}>
                Show all papers
              </Link>
            </Button>
          </div>
          <DueList rows={due.data?.results ?? []} />
        </section>
      ) : (
        <>
          {overview.due_count > 0 ? (
            <Card className="focus-within:ring-[3px] focus-within:ring-ring/40 hover:shadow-(--shadow-soft)">
              <Link to="/app/revision" className="flex items-center gap-3 rounded-xl p-4 outline-none">
                <span className="flex-1 font-semibold">Due for revision ({overview.due_count})</span>
                <ChevronRight aria-hidden className="size-5 text-muted-foreground" />
              </Link>
            </Card>
          ) : null}
          <SubjectProgressList
            groups={overview.groups}
            subjects={overview.subjects}
            electives={overview.electives}
            weighted={weighted}
            view={search.view}
          />
          {overview.electives.length > 0 ? (
            <ElectivePicker
              slots={overview.electives}
              pending={setElectives.isPending}
              error={setElectives.isError ? 'We could not save your elective. Please try again.' : undefined}
              onChange={(slotKey, subjectId) =>
                setElectives.mutate({ enrollmentId: overview.enrollment.id, choices: { [slotKey]: subjectId } })
              }
            />
          ) : null}
          <ReportIssue nodeType="level" nodeId={overview.enrollment.level.id} />
        </>
      )}
    </>
  )
}

export function SyllabusMapContainer({ search }: { search: MapSearch }) {
  return <CoverageShell>{(overview) => <Map overview={overview} search={search} />}</CoverageShell>
}
