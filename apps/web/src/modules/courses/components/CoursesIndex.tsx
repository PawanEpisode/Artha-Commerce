import { Container } from '@artha/design-system'
import type { ReactNode } from 'react'

import type { PublicCourse } from '../lib/load'
import { CoursesTable } from './CoursesTable'

/** The course catalog. Signed-in students see it inside the app frame. */
export function CoursesIndex({ courses, prompt }: { courses: PublicCourse[]; prompt?: ReactNode }) {
  return (
    <Container className="py-6 sm:py-8">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Courses</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          CA, CS and CMA. Open a course to read its papers and chapters. Tick what you have finished once you are signed
          in.
        </p>
      </header>
      <div className="mt-5 space-y-3">
        {prompt}
        <CoursesTable courses={courses} />
      </div>
    </Container>
  )
}
