import { createFileRoute } from '@tanstack/react-router'

import { FeaturesIndexContainer } from '~/modules/features'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/features/')({
  head: () => pageHead('/features'),
  component: FeaturesIndexContainer,
})
