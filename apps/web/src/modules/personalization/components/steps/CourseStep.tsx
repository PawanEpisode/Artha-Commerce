import { Alert, Skeleton } from '@artha/design-system'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { CourseLevelStep, ElectiveStep, prefillSelection, TermStep } from '~/modules/coverage'
import { fetchCourses, fetchLevel, fetchTerms } from '~/modules/syllabus'

import { useSaveStep } from '../../hooks/useOnboarding'
import { describeStepError } from '../../lib/stepErrors'
import type { StepProps } from './types'

type Stage = 'course' | 'term' | 'electives'

interface Props extends StepProps {
  /** Public course and level from `/courses` (`?course=ca&level=final`), so the first choice is already made. */
  initialCourse?: string
  initialLevel?: string
}

/**
 * Step 2: course and level, attempt and optional exam date, electives where the level has them. The three screens
 * share one draft and ONE save (`PUT .../steps/course/`), so a half-finished choice never creates an enrolment.
 */
export function CourseStep({ bootstrap, onDone, initialCourse, initialLevel }: Props) {
  const save = useSaveStep('course')
  const [stage, setStage] = useState<Stage>('course')
  const [course, setCourse] = useState(bootstrap.course?.course.code.toLowerCase() ?? '')
  const [level, setLevel] = useState(bootstrap.course?.level.code ?? '')
  const [termId, setTermId] = useState('')
  const [examDate, setExamDate] = useState('')
  const [choices, setChoices] = useState<Record<string, string>>({})
  const applied = useRef(false)

  const courses = useQuery({ queryKey: ['syllabus', 'courses'], queryFn: fetchCourses, staleTime: 5 * 60_000 })
  const syllabus = useQuery({
    queryKey: ['syllabus', 'level', course, level],
    queryFn: () => fetchLevel(course, level),
    enabled: Boolean(course && level),
  })
  const terms = useQuery({
    queryKey: ['syllabus', 'terms', course, level],
    queryFn: () => fetchTerms(course, level),
    enabled: Boolean(course && level),
  })

  // A course picked on the public pages is applied once, unless the student already has one.
  useEffect(() => {
    if (applied.current || !courses.data || !initialCourse || bootstrap.course) return
    const next = prefillSelection(courses.data, initialCourse, initialLevel)
    if (!next.course) return
    applied.current = true
    setCourse(next.course)
    setLevel(next.level)
  }, [courses.data, initialCourse, initialLevel, bootstrap.course])

  // The saved attempt comes back as a code; find its id once the terms are known.
  useEffect(() => {
    const saved = bootstrap.course?.term?.code
    if (saved && terms.data && !termId) setTermId(terms.data.find((t) => t.code === saved)?.id ?? '')
  }, [bootstrap.course?.term?.code, terms.data, termId])

  const scheme = syllabus.data?.scheme ?? null
  const slots = syllabus.data?.elective_slots ?? []
  const failure = save.error ? describeStepError(save.error) : null

  function submit() {
    if (!scheme) return
    save.mutate(
      {
        scheme: scheme.id,
        target_term: termId || null,
        ...(examDate ? { exam_date: examDate } : {}),
        ...(Object.keys(choices).length ? { electives: choices } : {}),
      },
      { onSuccess: onDone },
    )
  }

  function choose(slotKey: string, subjectId: string | null) {
    setChoices((prev) => {
      const next = { ...prev }
      if (subjectId) next[slotKey] = subjectId
      else delete next[slotKey]
      return next
    })
  }

  if (courses.isPending) return <Skeleton className="h-64 w-full" aria-busy />
  if (courses.isError)
    return <Alert variant="error">We could not load the course list. Refresh the page to try again.</Alert>

  if (stage === 'course') {
    return (
      <CourseLevelStep
        courses={courses.data ?? []}
        course={course}
        level={level}
        schemeName={scheme?.name ?? null}
        schemeLoading={Boolean(course && level) && syllabus.isPending}
        onCourse={(c) => {
          setCourse(c)
          setLevel('')
          setTermId('')
          setChoices({})
        }}
        onLevel={(l) => {
          setLevel(l)
          setTermId('')
          setChoices({})
        }}
        onNext={() => setStage('term')}
      />
    )
  }
  if (stage === 'term') {
    return (
      <TermStep
        terms={terms.data ?? []}
        termId={termId}
        examDate={examDate}
        pending={save.isPending}
        hasElectives={slots.length > 0}
        error={failure?.message}
        submitLabel={slots.length ? undefined : 'Continue'}
        onTerm={setTermId}
        onExamDate={setExamDate}
        onBack={() => setStage('course')}
        onSubmit={() => (slots.length ? setStage('electives') : submit())}
      />
    )
  }
  return (
    <ElectiveStep
      slots={slots}
      choices={choices}
      pending={save.isPending}
      error={failure?.message}
      submitLabel="Continue"
      onChoose={choose}
      onBack={() => setStage('term')}
      onSubmit={submit}
    />
  )
}
