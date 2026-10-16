import { createFileRoute } from '@tanstack/react-router'

import { faqItems, LandingPage } from '~/modules/landing'
import { publicPage } from '~/modules/layout'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/')({
  staticData: publicPage,
  head: () => pageHead('/', { faq: faqItems }),
  component: LandingPage,
})
