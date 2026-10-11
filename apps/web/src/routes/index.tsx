import { createFileRoute } from '@tanstack/react-router'

import { loadCourses } from '~/modules/courses'
import { faqItems, LandingPage } from '~/modules/landing'
import { publicPage } from '~/modules/layout'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/')({
  staticData: publicPage,
  loader: () => loadCourses(),
  head: () => pageHead('/', { faq: faqItems }),
  component: function HomeRoute() {
    const courses = Route.useLoaderData()
    return <LandingPage courses={courses} />
  },
})
