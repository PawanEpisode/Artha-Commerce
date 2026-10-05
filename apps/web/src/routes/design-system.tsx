import { createFileRoute } from '@tanstack/react-router'

import { DesignShowcase } from '~/modules/design-showcase'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/design-system')({
  head: () => pageHead('/design-system'),
  component: DesignShowcase,
})
