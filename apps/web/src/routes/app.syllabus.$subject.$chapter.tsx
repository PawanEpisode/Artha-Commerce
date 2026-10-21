import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { ChapterContainer } from '~/modules/coverage'
import { MaterialPanel } from '~/modules/material'
import { ChapterNotesSlot } from '~/modules/notes'
import { ChapterRecallSlot } from '~/modules/recall'
import { buildHead } from '~/modules/seo'
import { useAutoCapture } from '~/modules/tracker'

export const Route = createFileRoute('/app/syllabus/$subject/$chapter')({
  head: () =>
    buildHead({
      title: 'Chapter coverage',
      description: 'Your progress in this chapter.',
      path: '/app/syllabus',
      noindex: true,
    }),
  component: function ChapterRoute() {
    const { subject, chapter } = Route.useParams()
    const navigate = useNavigate()
    useAutoCapture(chapter)

    return (
      <ChapterContainer
        subjectId={subject}
        chapterId={chapter}
        renderNotes={({ subjectKey, chapterKey }) => (
          <div className="space-y-6">
            <MaterialPanel
              workKey={subjectKey}
              chapterKey={chapterKey}
              onOpenWork={(wk) =>
                navigate({
                  to: '/app/material/$workKey',
                  params: { workKey: wk },
                })
              }
              onSelectItem={(item) =>
                navigate({
                  to: '/app/material/item/$itemId',
                  params: { itemId: item.id },
                })
              }
            />
            <ChapterNotesSlot subjectKey={subjectKey} chapterKey={chapterKey} />
            <ChapterRecallSlot chapterId={chapter} />
          </div>
        )}
      />
    )
  },
})
