import { createFileRoute, notFound } from '@tanstack/react-router'

import { fetchPublicDocument, PublicDocumentContainer } from '~/modules/amendments'
import { publicPage } from '~/modules/layout'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/amendments/documents/$slug')({
  staticData: publicPage,
  loader: async ({ params }) => {
    const doc = await fetchPublicDocument(params.slug)
    if (!doc) throw notFound()
    return { doc }
  },
  head: ({ loaderData }) =>
    buildHead({
      title: loaderData?.doc ? `${loaderData.doc.title} | Statutory Amendments` : 'Statutory Amendment Document',
      description: loaderData?.doc
        ? `Official ${loaderData.doc.issuer_label} amendment notifications, revision ${loaderData.doc.revision_no}, with attempt-wise applicability.`
        : 'Official statutory and academic amendments notification.',
      path: `/amendments/documents/${loaderData?.doc?.slug ?? ''}`,
    }),
  component: function DocumentRoute() {
    const { doc } = Route.useLoaderData()
    return <PublicDocumentContainer document={doc} />
  },
})
