import { createFileRoute } from '@tanstack/react-router'

import { env } from '~/lib/env'
import { fetchPublicCard } from '~/modules/amendments'
import { amendmentCard, DEFAULT_OG_IMAGE, ogResponse } from '~/modules/seo'
// Deliberately not in the seo barrel: it loads native code that must only ever reach the server bundle.
import { renderOgPng } from '~/modules/seo/og-render'

/** Preview image of an amendment change card page. Falls back to the site image on any failure. */
export const Route = createFileRoute('/og/amendments/$cardId')({
  server: {
    handlers: {
      GET: async ({ params }) => {
        try {
          const card = await fetchPublicCard(params.cardId)
          if (!card) return ogResponse.notFound()
          const og = amendmentCard({
            title: card.title,
            lawLabel: card.law_label,
            provisionLabel: card.provision_label,
            courseLevel: card.law_label,
            changeType: card.change_type,
          })
          return ogResponse.png(await renderOgPng(og, env.VITE_SITE_NAME))
        } catch (error) {
          console.error('amendment og image failed', error)
          return ogResponse.fallback(DEFAULT_OG_IMAGE)
        }
      },
    },
  },
})
