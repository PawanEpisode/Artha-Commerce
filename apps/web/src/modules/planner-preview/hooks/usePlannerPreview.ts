import { useMemo, useState } from 'react'

import { courses, type CourseSlug } from '~/modules/catalog'

import { buildPlan } from '../lib/plan'

export function usePlannerPreview() {
  const [courseSlug, setCourseSlug] = useState<CourseSlug>('ca')
  const [levelIndex, setLevelIndex] = useState(1)
  const [months, setMonths] = useState(6)
  const [hoursPerDay, setHoursPerDay] = useState(5)

  const course = courses.find((c) => c.slug === courseSlug) ?? courses[0]
  const level = course.levels[Math.min(levelIndex, course.levels.length - 1)]
  const plan = useMemo(() => buildPlan({ subjects: level.subjects, months, hoursPerDay }), [level, months, hoursPerDay])

  return {
    course,
    level,
    plan,
    months,
    hoursPerDay,
    levelIndex,
    selectCourse: (slug: CourseSlug) => {
      setCourseSlug(slug)
      setLevelIndex(1)
    },
    setLevelIndex,
    setMonths,
    setHoursPerDay,
  }
}
