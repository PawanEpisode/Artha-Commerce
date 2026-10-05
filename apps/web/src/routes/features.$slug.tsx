import { createFileRoute, notFound } from '@tanstack/react-router'

import { getFeature } from '~/modules/catalog'
import { FeatureDetailContainer } from '~/modules/features'
import { featureHead } from '~/modules/seo'

export const Route = createFileRoute('/features/$slug')({
  loader: ({ params }) => {
    const feature = getFeature(params.slug)
    if (!feature) throw notFound()
    return { feature }
  },
  head: ({ loaderData }) => (loaderData ? featureHead(loaderData.feature) : {}),
  component: function FeatureRoute() {
    const { feature } = Route.useLoaderData()
    return <FeatureDetailContainer feature={feature} />
  },
})
