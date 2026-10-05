import { Alert, Container, Skeleton, Stepper } from '@artha/design-system'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Navigate, useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { fetchCourses, fetchLevel, fetchTerms } from '~/modules/syllabus'

import { CatchupResult } from '../components/CatchupResult'
import { CatchupStep } from '../components/CatchupStep'
import { CourseLevelStep, ElectiveStep, TermStep } from '../components/OnboardingSteps'
import { useCatchup, useCreateEnrollment } from '../hooks/useCoverageMutations'
import { useOverview } from '../hooks/useCoverageQueries'
import { getSubject } from '../lib/api'
import { coverageKeys } from '../lib/keys'
import { prefillSelection } from '../lib/prefill'
import type { Overview } from '../lib/types'

type Stage = 'course' | 'term' | 'electives' | 'catchup'

/** The first-run flow (PRD 5.1): course, level, attempt, elective papers (where the level has them), then Quick catch-up and the aha moment. */
export function OnboardingContainer({
  initialCourse,
  initialLevel,
}: {
  /** Public course slug, from /courses, so the first step opens already chosen. */
  initialCourse?: string
  initialLevel?: string
}) {
  const enabled = useFeatureFlag('syllabus_coverage')
  const navigate = useNavigate()
  const overview = useOverview()
  const [stage, setStage] = useState<Stage>('course')
  const [course, setCourse] = useState('')
  const [level, setLevel] = useState('')
  const applied = useRef(false)
  const [termId, setTermId] = useState('')
  const [examDate, setExamDate] = useState('')
  const [dailyHours, setDailyHours] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [electiveChoices, setElectiveChoices] = useState<Record<string, string>>({})
  const [alsoRevised, setAlsoRevised] = useState(false)
  const [created, setCreated] = useState(false)

  const courses = useQuery({ queryKey: ['syllabus', 'courses'], queryFn: fetchCourses, staleTime: 5 * 60_000 })
  useEffect(() => {
    if (applied.current || !courses.data || !initialCourse) return
    const next = prefillSelection(courses.data, initialCourse, initialLevel)
    if (!next.course) return
    applied.current = true
    setCourse(next.course)
    setLevel(next.level)
  }, [courses.data, initialCourse, initialLevel])
  const levelSyllabus = useQuery({
    queryKey: ['syllabus', 'level', course, level],
    queryFn: () => fetchLevel(course, level),
    enabled: Boolean(course && level),
  })
  const terms = useQuery({
    queryKey: ['syllabus', 'terms', course, level],
    queryFn: () => fetchTerms(course, level),
    enabled: Boolean(course && level),
  })
  const enroll = useCreateEnrollment()
  const catchup = useCatchup()

  const ov = overview.data
  // Papers of an elective the student did not choose are out of their syllabus, so they are not offered for catch-up.
  const subjects = useMemo(() => {
    const chosen = new Map((ov?.electives ?? []).map((slot) => [slot.key, slot.chosen]))
    return (ov?.subjects ?? []).filter((s) => !s.elective_slot || chosen.get(s.elective_slot) === s.id)
  }, [ov])
  const chapterQueries = useQueries({
    queries: subjects.map((s) => ({
      queryKey: coverageKeys.subject(s.id),
      queryFn: () => getSubject(s.id),
      enabled: created,
    })),
  })

  const hiddenElectives = (ov?.subjects.length ?? 0) > subjects.length
  const catchupSubjects = useMemo(
    () => subjects.map((subject, i) => ({ subject, chapters: chapterQueries[i]?.data?.chapters })),
    [subjects, chapterQueries],
  )

  if (!enabled || overview.featureDisabled) return <Navigate to="/app" replace />
  // Already enrolled (and not in the middle of this flow): straight to the map.
  if (ov && !created) return <Navigate to="/app/syllabus" replace />

  const scheme = levelSyllabus.data?.scheme ?? null
  const slots = levelSyllabus.data?.elective_slots ?? []
  const steps = slots.length ? ['Course', 'Exam', 'Electives', 'Catch up'] : ['Course', 'Exam', 'Catch up']

  function createNow() {
    if (!scheme) return
    enroll.mutate(
      {
        scheme: scheme.id,
        target_term: termId || null,
        exam_date: examDate || null,
        daily_hours: dailyHours.trim() === '' ? null : Number(dailyHours),
        ...(Object.keys(electiveChoices).length ? { electives: electiveChoices } : {}),
      },
      {
        onSuccess: () => {
          setCreated(true)
          setStage('catchup')
        },
      },
    )
  }

  function chooseElective(slotKey: string, subjectId: string | null) {
    setElectiveChoices((prev) => {
      const next = { ...prev }
      if (subjectId) next[slotKey] = subjectId
      else delete next[slotKey]
      return next
    })
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
  const stageIndex = stage === 'course' ? 0 : stage === 'term' ? 1 : stage === 'electives' ? 2 : steps.length - 1
  const stepIndex = done ? steps.length : stageIndex

  return (
    <Container className="max-w-2xl space-y-8 py-10 sm:py-16">
      <header className="space-y-4">
        <h1 className="font-display text-3xl font-extrabold">Set up My Coverage</h1>
        <Stepper steps={steps} current={Math.min(stepIndex, steps.length - 1)} />
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
      ) : stage === 'course' ? (
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
            setElectiveChoices({})
          }}
          onLevel={(l) => {
            setLevel(l)
            setTermId('')
            setElectiveChoices({})
          }}
          onNext={() => setStage('term')}
        />
      ) : stage === 'term' ? (
        <TermStep
          terms={terms.data ?? []}
          termId={termId}
          examDate={examDate}
          dailyHours={dailyHours}
          pending={enroll.isPending}
          hasElectives={slots.length > 0}
          error={enroll.isError ? 'We could not create your syllabus map. Please try again.' : undefined}
          onTerm={setTermId}
          onExamDate={setExamDate}
          onDailyHours={setDailyHours}
          onBack={() => setStage('course')}
          onSubmit={() => (slots.length ? setStage('electives') : createNow())}
        />
      ) : stage === 'electives' ? (
        <ElectiveStep
          slots={slots}
          choices={electiveChoices}
          pending={enroll.isPending}
          error={enroll.isError ? 'We could not create your syllabus map. Please try again.' : undefined}
          onChoose={chooseElective}
          onBack={() => setStage('term')}
          onSubmit={createNow}
        />
      ) : (
        <CatchupStep
          subjects={catchupSubjects}
          selected={selected}
          alsoRevised={alsoRevised}
          pending={catchup.isPending}
          error={catchup.isError ? 'We could not apply that. Please try again.' : undefined}
          note={
            hiddenElectives
              ? 'Elective papers you have not chosen are not listed. You can choose them later from your syllabus map.'
              : undefined
          }
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
