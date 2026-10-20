import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { MyAmendmentsContainer } from '~/modules/amendments'
import { buildHead } from '~/modules/seo'

const amendmentsSearchSchema = z.object({
  term: z.string().optional(),
  subject: z.string().optional(),
  type: z.string().optional(),
})

export const Route = createFileRoute('/app/amendments/')({
  validateSearch: amendmentsSearchSchema,
  head: () =>
    buildHead({
      title: 'Amendments Engine',
      description: 'Official statutory and academic amendments curated and mapped to your syllabus.',
      path: '/app/amendments',
      noindex: true,
    }),
  component: MyAmendmentsContainer,
})
