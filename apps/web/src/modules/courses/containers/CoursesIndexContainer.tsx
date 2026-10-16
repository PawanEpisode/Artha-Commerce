import { useEffect } from 'react'

import { useAuth } from '~/modules/auth'
import { track } from '~/modules/observability'

import { CoursesIndex } from '../components/CoursesIndex'
import type { PublicCourse } from '../lib/load'
import { CoveragePrompt } from './CoveragePrompt'

/** The course catalog. Signed-in students browse it inside the app frame; `?all=1` is kept so old links still work. */
export function CoursesIndexContainer({
  courses,
  exploreAll = false,
}: {
  courses: PublicCourse[]
  exploreAll?: boolean
}) {
  const { user, loading } = useAuth()
  const signedIn = !loading && Boolean(user)

  useEffect(() => {
    if (signedIn && exploreAll) track('courses_scope_toggled', { all: true })
  }, [signedIn, exploreAll])

  return <CoursesIndex courses={courses} prompt={signedIn ? <CoveragePrompt surface="home" /> : undefined} />
}
