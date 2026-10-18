import { Info } from '@artha/design-system'

export interface DisclaimerNoteProps {
  className?: string
}

/**
 * Standing legal & statistical disclaimer required by PRD 7.5.
 * Strictly avoids any guarantee or prediction claims.
 */
export function DisclaimerNote({ className }: DisclaimerNoteProps) {
  return (
    <div
      role="note"
      className={`flex items-start gap-2.5 rounded-lg border border-muted bg-muted/30 p-3 text-xs text-muted-foreground ${className || ''}`}
    >
      <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground/80" aria-hidden />
      <p className="leading-relaxed">
        <strong>Important notice:</strong> Based on past papers. History is not a guarantee. The Institute can ask from
        any chapter, so keep covering the whole syllabus.
      </p>
    </div>
  )
}
