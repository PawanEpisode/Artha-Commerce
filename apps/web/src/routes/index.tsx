import { createFileRoute } from '@tanstack/react-router'
import { LandingPage, faqItems } from '~/modules/landing'
import { buildHead, faqJsonLd, organizationJsonLd, websiteJsonLd } from '~/modules/seo'

export const Route = createFileRoute('/')({
  head: () =>
    buildHead({
      title: 'ArthaCommerce: Exam Preparation Workspace for CA, CS and CMA',
      description:
        'Plan your study, track every chapter, practise mock tests and revise smarter. The exam preparation workspace for CA, CS and CMA students in India.',
      path: '/',
      jsonLd: [organizationJsonLd(), websiteJsonLd(), faqJsonLd(faqItems)],
    }),
  component: LandingPage,
})
