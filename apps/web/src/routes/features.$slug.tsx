import { createFileRoute, notFound } from '@tanstack/react-router'

import { getFeature } from '~/modules/catalog'
import { FeatureDetailContainer } from '~/modules/features'
import { breadcrumbJsonLd, buildHead } from '~/modules/seo'

export const Route = createFileRoute('/features/$slug')({
  loader: ({ params }) => {
    const feature = getFeature(params.slug)
    if (!feature) throw notFound()
    return { feature }
  },
  head: ({ loaderData }) => {
    if (!loaderData) return {}
    const { feature } = loaderData
    const path = `/features/${feature.slug}`
    return buildHead({
      title: feature.title,
      description: feature.description,
      path,
      jsonLd: breadcrumbJsonLd([
        { name: 'Home', path: '/' },
        { name: 'Features', path: '/features' },
        { name: feature.title, path },
      ]),
    })
  },
  component: function FeatureRoute() {
    const { feature } = Route.useLoaderData()
    return <FeatureDetailContainer feature={feature} />
  },
})
