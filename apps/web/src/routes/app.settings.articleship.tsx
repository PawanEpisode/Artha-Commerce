import { createFileRoute } from '@tanstack/react-router'

import { ArticleshipSettingsContainer } from '~/modules/progression'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/settings/articleship')({
  head: () =>
    buildHead({
      title: 'Articleship planner settings',
      description: 'Practical training lifestyle, weekday/weekend hours, and exam leave.',
      path: '/app/settings/articleship',
      noindex: true,
    }),
  component: ArticleshipSettingsContainer,
})
