import { Alert, SelectField } from '@artha/design-system'
import { useEffect, useId, useMemo, useState } from 'react'

import { useCourses, useLevelSubjects, useSubjectChapters } from '../hooks/useChapterPicker'

const NONE = ''

export interface PickedChapter {
  id: string
  name: string
}

/**
 * Course, level, paper, then chapter. A course with a single level, or an account with a single course, skips that
 * step. Picking a chapter reports it; changing an earlier step clears the chapter so a stale one is never kept.
 */
export function ChapterPicker({
  label = 'Chapter',
  onPick,
  disabled,
}: {
  label?: string
  onPick: (chapter: PickedChapter | null) => void
  disabled?: boolean
}) {
  const id = useId()
  const courses = useCourses()
  const [course, setCourse] = useState(NONE)
  const [level, setLevel] = useState(NONE)
  const [subject, setSubject] = useState(NONE)
  const [chapter, setChapter] = useState(NONE)

  const list = useMemo(() => courses.data ?? [], [courses.data])
  const levels = useMemo(() => list.find((c) => c.code === course)?.levels ?? [], [list, course])
  const subjects = useLevelSubjects(course, level)
  const chapters = useSubjectChapters(course, level, subject)

  // The only course (or the only level of it) is chosen for her.
  useEffect(() => {
    const only = list.length === 1 ? list[0] : undefined
    if (!course && only) setCourse(only.code)
  }, [course, list])
  useEffect(() => {
    const only = levels.length === 1 ? levels[0] : undefined
    if (course && !level && only) setLevel(only.code)
  }, [course, level, levels])

  const reset = (from: 'course' | 'level' | 'subject') => {
    if (from === 'course') setLevel(NONE)
    if (from === 'course' || from === 'level') setSubject(NONE)
    setChapter(NONE)
    onPick(null)
  }

  if (courses.isError) return <Alert variant="error">We could not load the syllabus. Try again in a moment.</Alert>

  return (
    <fieldset className="grid gap-3" disabled={disabled}>
      <legend className="text-sm font-medium">{label}</legend>
      <div className="grid gap-3 sm:grid-cols-2">
        {list.length > 1 ? (
          <SelectField
            aria-label="Course"
            id={`${id}-course`}
            value={course}
            onValueChange={(v) => {
              setCourse(v)
              reset('course')
            }}
            options={[
              { value: NONE, label: 'Choose a course' },
              ...list.map((c) => ({ value: c.code, label: c.name })),
            ]}
          />
        ) : null}
        {course && levels.length > 1 ? (
          <SelectField
            aria-label="Level"
            id={`${id}-level`}
            value={level}
            onValueChange={(v) => {
              setLevel(v)
              reset('level')
            }}
            options={[
              { value: NONE, label: 'Choose a level' },
              ...[...levels].sort((a, b) => a.sort_order - b.sort_order).map((l) => ({ value: l.code, label: l.name })),
            ]}
          />
        ) : null}
        {level ? (
          <SelectField
            aria-label="Paper"
            id={`${id}-paper`}
            value={subject}
            onValueChange={(v) => {
              setSubject(v)
              reset('subject')
            }}
            options={[
              { value: NONE, label: subjects.isPending ? 'Loading…' : 'Choose a paper' },
              ...(subjects.data ?? []).map((s) => ({ value: s.key, label: s.name })),
            ]}
          />
        ) : null}
        {subject ? (
          <SelectField
            aria-label="Chapter"
            id={`${id}-chapter`}
            value={chapter}
            onValueChange={(v) => {
              setChapter(v)
              const c = chapters.data?.find((x) => x.id === v)
              onPick(c ? { id: c.id, name: c.name } : null)
            }}
            options={[
              { value: NONE, label: chapters.isPending ? 'Loading…' : 'Choose a chapter' },
              ...(chapters.data ?? []).map((c) => ({ value: c.id, label: c.name })),
            ]}
          />
        ) : null}
      </div>
      {subjects.isError || chapters.isError ? (
        <Alert variant="error">We could not load that part of the syllabus. Pick again or try later.</Alert>
      ) : null}
    </fieldset>
  )
}
