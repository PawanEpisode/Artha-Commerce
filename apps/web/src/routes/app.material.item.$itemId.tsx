import { createFileRoute, useRouter } from '@tanstack/react-router'

import { ItemContainer } from '~/modules/material'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/material/item/$itemId')({
  head: () =>
    buildHead({
      title: 'Study Material Item & Deep Link',
      description: 'Official illustration, problem, or exercise detail with deep link reference.',
      path: '/app/material',
      noindex: true,
    }),
  component: function MaterialItemRoute() {
    const { itemId } = Route.useParams()
    const router = useRouter()

    return (
      <ItemContainer
        itemId={itemId}
        onBack={() => {
          if (window.history.length > 1) {
            router.history.back()
          } else {
            router.navigate({ to: '/app/material' })
          }
        }}
      />
    )
  },
})
