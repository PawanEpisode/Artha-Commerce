import { useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { useAuth } from '~/modules/auth'

import { CoursesIndex } from '../components/CoursesIndex'
import type { PublicCourse } from '../lib/load'
import { CoveragePrompt } from './CoveragePrompt'

/** Public catalog. A signed-in student belongs on the home, including when they arrive by a client navigation. */
export function CoursesIndexContainer({ courses }: { courses: PublicCourse[] }) {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const signedIn = !loading && Boolean(user)

  useEffect(() => {
    if (signedIn) void navigate({ to: '/', replace: true })
  }, [signedIn, navigate])

  if (signedIn) return null
  return <CoursesIndex courses={courses} prompt={<CoveragePrompt surface="home" />} />
}
