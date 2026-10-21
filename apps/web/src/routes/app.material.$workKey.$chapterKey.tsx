import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { ChapterItemsContainer } from '~/modules/material'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/material/$workKey/$chapterKey')({
  head: () =>
    buildHead({
      title: 'Chapter Study Material Checklist',
      description: 'Official chapter illustrations, exercises, solutions, and progress tracking.',
      path: '/app/material',
      noindex: true,
    }),
  component: function ChapterChecklistRoute() {
    const { workKey, chapterKey } = Route.useParams()
    const navigate = useNavigate()

    return (
      <ChapterItemsContainer
        workKey={workKey}
        chapterKey={chapterKey}
        onBackToWork={(targetWorkKey) =>
          navigate({
            to: '/app/material/$workKey',
            params: { workKey: targetWorkKey },
          })
        }
        onSelectItem={(item) =>
          navigate({
            to: '/app/material/item/$itemId',
            params: { itemId: item.id },
          })
        }
      />
    )
  },
})
