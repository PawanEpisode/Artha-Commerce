import { createFileRoute } from '@tanstack/react-router'

import { PdfReaderContainer, readerSearchSchema } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

/** The PDF reader: bare chrome (the reader draws its own bars), never indexed, rendered on the client only. */
export const Route = createFileRoute('/app/notes/pdf/$docId')({
  staticData: { chrome: 'bare' },
  ssr: false,
  validateSearch: readerSearchSchema,
  head: () =>
    buildHead({
      title: 'PDF reader',
      description: 'Read and mark a PDF.',
      path: '/app/notes',
      noindex: true,
    }),
  component: function PdfReaderRoute() {
    const { docId } = Route.useParams()
    const search = Route.useSearch()
    const navigate = Route.useNavigate()
    return (
      <PdfReaderContainer
        docId={docId}
        search={search}
        onSearchChange={(patch) => void navigate({ search: (prev) => ({ ...prev, ...patch }), replace: true })}
        onBack={() => (window.history.length > 1 ? window.history.back() : void navigate({ to: '/app/notes' }))}
      />
    )
  },
})
