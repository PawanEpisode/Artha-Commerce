import { createFileRoute } from '@tanstack/react-router'

import { faqItems, LandingPage } from '~/modules/landing'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/')({
  head: () => pageHead('/', { faq: faqItems }),
  component: LandingPage,
})
