import { createFileRoute, notFound } from '@tanstack/react-router'

import { fetchPublicCard, PublicCardDetailContainer } from '~/modules/amendments'
import { publicPage } from '~/modules/layout'
import { amendmentOgPath, buildHead } from '~/modules/seo'

export const Route = createFileRoute('/amendments/cards/$publicId')({
  staticData: publicPage,
  loader: async ({ params }) => {
    const card = await fetchPublicCard(params.publicId)
    if (!card) throw notFound()
    return { card }
  },
  head: ({ loaderData }) =>
    buildHead({
      title: loaderData?.card ? `${loaderData.card.title} | ${loaderData.card.law_label}` : 'Statutory Amendment Card',
      description: loaderData?.card
        ? `${loaderData.card.law_label} ${loaderData.card.provision_label}: ${loaderData.card.title}. 4-eye verified statutory comparison.`
        : 'Verified statutory amendment provision with before-and-after comparison.',
      path: `/amendments/cards/${loaderData?.card?.public_id ?? ''}`,
      image: loaderData?.card ? amendmentOgPath(loaderData.card.public_id) : undefined,
    }),
  component: function PublicCardRoute() {
    const { card } = Route.useLoaderData()
    return <PublicCardDetailContainer card={card} />
  },
})
