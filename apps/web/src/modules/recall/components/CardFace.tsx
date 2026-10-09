import { Badge } from '@artha/design-system'

import { InlineText } from './InlineText'

const KIND_LABELS: Record<string, string> = {
  pointer: 'Pointer',
  formula: 'Formula',
  section: 'Section',
  definition: 'Definition',
  mnemonic: 'Mnemonic',
  case_law: 'Case law',
  cloze: 'Fill in the blank',
}

export const kindLabel = (kind: string): string => KIND_LABELS[kind] ?? 'Card'

/** One side of a card: its kind and chapter as small labels, then the text. */
export function CardFace({
  text,
  kind,
  chapter,
  side,
}: {
  text: string
  kind: string
  chapter?: string | null
  side: 'front' | 'back'
}) {
  return (
    <>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Badge variant="outline">{kindLabel(kind)}</Badge>
        {chapter ? <span className="text-xs text-muted-foreground">{chapter}</span> : null}
        <span className="sr-only">{side === 'front' ? 'Question' : 'Answer'}</span>
      </div>
      <div className="space-y-3 text-lg leading-relaxed text-foreground sm:text-xl">
        <InlineText text={text} />
      </div>
    </>
  )
}
