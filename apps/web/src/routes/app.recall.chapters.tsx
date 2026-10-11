import { createFileRoute } from '@tanstack/react-router'

import { ChapterRemapContainer } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/recall/chapters')({
  head: () =>
    buildHead({
      title: 'Needs a new chapter',
      description: 'Pick a chapter of your new syllabus for your own cards.',
      path: '/app/recall/chapters',
      noindex: true,
    }),
  component: ChapterRemapContainer,
})
