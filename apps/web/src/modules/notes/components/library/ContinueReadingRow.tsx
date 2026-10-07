import type { DocumentSummary } from '../../lib/document-types'
import { DocumentCard } from './DocumentCard'

/** "Continue reading": up to three ready PDFs the student opened last, each with a link to the page they stopped on. */
export function ContinueReadingRow({ items }: { items: readonly DocumentSummary[] }) {
  if (items.length === 0) return null
  return (
    <section aria-labelledby="continue-h" className="space-y-3">
      <h2 id="continue-h" className="font-display text-xl font-bold">
        Continue reading
      </h2>
      <ul className="grid gap-3 sm:grid-cols-3">
        {items.slice(0, 3).map((doc) => (
          <li key={doc.id} className="min-w-0">
            <DocumentCard doc={doc} compact showLocation={false} resume className="h-full" />
          </li>
        ))}
      </ul>
    </section>
  )
}
