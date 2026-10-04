import { Alert, Container, Skeleton, Stepper } from '@artha/design-system'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Navigate, useNavigate } from '@tanstack/react-router'
import { useMemo, useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { fetchCourses, fetchLevel, fetchTerms } from '~/modules/syllabus'

import { CatchupResult } from '../components/CatchupResult'
import { CatchupStep } from '../components/CatchupStep'
import { CourseLevelStep, TermStep } from '../components/OnboardingSteps'
import { useCatchup, useCreateEnrollment } from '../hooks/useCoverageMutations'
import { useOverview } from '../hooks/useCoverageQueries'
import { getSubject } from '../lib/api'
import { coverageKeys } from '../lib/keys'
import type { Overview } from '../lib/types'

const STEPS = ['Course', 'Exam', 'Catch up']

/** The first-run flow (PRD 5.1): course, level, attempt, then Quick catch-up and the aha moment. */
export function OnboardingContainer() {
  const enabled = useFeatureFlag('syllabus_coverage')
  const navigate = useNavigate()
  const overview = useOverview()
  const [step, setStep] = useState(0)
  const [course, setCourse] = useState('')
  const [level, setLevel] = useState('')
  const [termId, setTermId] = useState('')
  const [examDate, setExamDate] = useState('')
  const [dailyHours, setDailyHours] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [alsoRevised, setAlsoRevised] = useState(false)
  const [created, setCreated] = useState(false)

  const courses = useQuery({ queryKey: ['syllabus', 'courses'], queryFn: fetchCourses, staleTime: 5 * 60_000 })
  const levelSyllabus = useQuery({
    queryKey: ['syllabus', 'level', course, level],
    queryFn: () => fetchLevel(course, level),
    enabled: Boolean(course && level),
  })
  const terms = useQuery({
    queryKey: ['syllabus', 'terms', course],
    queryFn: () => fetchTerms(course),
    enabled: Boolean(course),
  })
  const enroll = useCreateEnrollment()
  const catchup = useCatchup()

  const ov = overview.data
  const subjects = useMemo(() => ov?.subjects ?? [], [ov])
  const chapterQueries = useQueries({
    queries: subjects.map((s) => ({
      queryKey: coverageKeys.subject(s.id),
      queryFn: () => getSubject(s.id),
      enabled: created,
    })),
  })

  const catchupSubjects = useMemo(
    () => subjects.map((subject, i) => ({ subject, chapters: chapterQueries[i]?.data?.chapters })),
    [subjects, chapterQueries],
  )

  if (!enabled) return <Navigate to="/app" replace />
  // Already enrolled (and not in the middle of this flow): straight to the map.
  if (ov && !created) return <Navigate to="/app/syllabus" replace />

  const scheme = levelSyllabus.data?.scheme ?? null

  function createNow() {
    if (!scheme) return
    enroll.mutate(
      {
        scheme: scheme.id,
        target_term: termId || null,
        exam_date: examDate || null,
        daily_hours: dailyHours.trim() === '' ? null : Number(dailyHours),
      },
      {
        onSuccess: () => {
          setCreated(true)
          setStep(2)
        },
      },
    )
  }

  function toggleChapter(id: string, on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (on) next.add(id)
      else next.delete(id)
      return next
    })
  }

  function toggleSubject(ids: string[], on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev)
      for (const id of ids) {
        if (on) next.add(id)
        else next.delete(id)
      }
      return next
    })
  }

  function startWith(result: Overview) {
    const lowest = [...result.subjects]
      .filter((s) => s.chapters_total > 0)
      .sort((a, b) => a.pct_simple - b.pct_simple)[0]
    if (!lowest) return null
    const chapters = chapterQueries[subjects.findIndex((s) => s.id === lowest.id)]?.data?.chapters ?? []
    return {
      name: lowest.name,
      notStarted: chapters.filter((c) => c.status === 'not_started' && !selected.has(c.id)).length,
    }
  }

  const done = catchup.data?.overview
  const stepIndex = done ? 3 : step

  return (
    <Container className="max-w-2xl space-y-8 py-10 sm:py-16">
      <header className="space-y-4">
        <h1 className="font-display text-3xl font-extrabold">Set up My Coverage</h1>
        <Stepper steps={STEPS} current={Math.min(stepIndex, STEPS.length - 1)} />
      </header>

      {courses.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : courses.isError ? (
        <Alert variant="error">We could not load the course list. Please refresh and try again.</Alert>
      ) : done ? (
        <CatchupResult
          levelName={`${done.enrollment.course.name} ${done.enrollment.level.name}`}
          percent={done.level.pct_simple}
          startWith={startWith(done)}
        />
      ) : step === 0 ? (
        <CourseLevelStep
          courses={courses.data ?? []}
          course={course}
          level={level}
          schemeName={scheme?.name ?? null}
          schemeLoading={Boolean(course && level) && levelSyllabus.isPending}
          onCourse={(c) => {
            setCourse(c)
            setLevel('')
            setTermId('')
          }}
          onLevel={setLevel}
          onNext={() => setStep(1)}
        />
      ) : step === 1 ? (
        <TermStep
          terms={terms.data ?? []}
          termId={termId}
          examDate={examDate}
          dailyHours={dailyHours}
          pending={enroll.isPending}
          error={enroll.isError ? 'We could not create your syllabus map. Please try again.' : undefined}
          onTerm={setTermId}
          onExamDate={setExamDate}
          onDailyHours={setDailyHours}
          onBack={() => setStep(0)}
          onSubmit={createNow}
        />
      ) : (
        <CatchupStep
          subjects={catchupSubjects}
          selected={selected}
          alsoRevised={alsoRevised}
          pending={catchup.isPending}
          error={catchup.isError ? 'We could not apply that. Please try again.' : undefined}
          onToggleChapter={toggleChapter}
          onToggleSubject={toggleSubject}
          onAlsoRevised={setAlsoRevised}
          onApply={() => catchup.mutate({ chapterIds: [...selected], alsoRevised })}
          onSkip={() => void navigate({ to: '/app/syllabus' })}
        />
      )}
    </Container>
  )
}
