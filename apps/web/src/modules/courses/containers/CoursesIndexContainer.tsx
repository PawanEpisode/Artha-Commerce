import { useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { useAuth } from '~/modules/auth'

import { CoursesIndex } from '../components/CoursesIndex'
import type { PublicCourse } from '../lib/load'
import { CoveragePrompt } from './CoveragePrompt'

/** Public catalog. A signed-in student belongs on the home (unless they chose `?all=1`), including when they arrive by a client navigation. */
export function CoursesIndexContainer({
  courses,
  exploreAll = false,
}: {
  courses: PublicCourse[]
  exploreAll?: boolean
}) {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const signedIn = !loading && Boolean(user)
  const redirect = signedIn && !exploreAll

  useEffect(() => {
    if (redirect) void navigate({ to: '/', replace: true })
  }, [redirect, navigate])

  if (redirect) return null
  return <CoursesIndex courses={courses} prompt={<CoveragePrompt surface="home" />} backHome={signedIn} />
}
