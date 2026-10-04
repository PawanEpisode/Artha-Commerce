import { Badge } from '@artha/design-system'

import type { SyllabusScheme } from '../lib/types'

/** Scheme name and where the syllabus comes from, so students can verify it. */
export function SyllabusMeta({ scheme, body }: { scheme: SyllabusScheme; body: string }) {
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
      <Badge variant="outline">{scheme.name}</Badge>
      {scheme.source_url ? (
        <a
          href={scheme.source_url}
          rel="noopener noreferrer"
          target="_blank"
          className="font-medium text-primary underline underline-offset-4"
        >
          Official source ({body})
        </a>
      ) : (
        <span>Confirm with {body} before relying on it.</span>
      )}
    </p>
  )
}
