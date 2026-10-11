import { createFileRoute } from '@tanstack/react-router'

import { FeaturesIndexContainer } from '~/modules/features'
import { publicPage } from '~/modules/layout'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/features/')({
  staticData: publicPage,
  head: () => pageHead('/features'),
  component: FeaturesIndexContainer,
})
