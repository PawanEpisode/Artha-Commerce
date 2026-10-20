import { createFileRoute } from '@tanstack/react-router'

import { fetchPublicHub, PublicAmendmentsHubContainer } from '~/modules/amendments'
import { publicPage } from '~/modules/layout'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/amendments/')({
  staticData: publicPage,
  loader: () => fetchPublicHub(),
  head: () => pageHead('/amendments'),
  component: function AmendmentsHubRoute() {
    const hub = Route.useLoaderData()
    return <PublicAmendmentsHubContainer hub={hub} />
  },
})
