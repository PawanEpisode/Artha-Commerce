import { createFileRoute } from '@tanstack/react-router'

import { DesignShowcase } from '~/modules/design-showcase'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/design-system')({
  head: () =>
    buildHead({
      title: 'Design system',
      description: 'Internal style guide for ArthaCommerce.',
      path: '/design-system',
      noindex: true,
    }),
  component: DesignShowcase,
})
