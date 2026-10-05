import { createFileRoute } from '@tanstack/react-router'

import { loadCourses } from '~/modules/courses'
import { faqItems, LandingPage } from '~/modules/landing'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/')({
  loader: () => loadCourses(),
  head: () => pageHead('/', { faq: faqItems }),
  component: function HomeRoute() {
    const courses = Route.useLoaderData()
    return <LandingPage courses={courses} />
  },
})
