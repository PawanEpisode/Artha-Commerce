import { createFileRoute } from '@tanstack/react-router'
import { CoursesIndex } from '~/modules/courses'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/courses/')({
  head: () =>
    buildHead({
      title: 'CA, CS and CMA Courses',
      description: 'Explore Foundation, Intermediate/Executive and Final/Professional levels for CA, CS and CMA exam preparation.',
      path: '/courses',
    }),
  component: CoursesIndex,
})
