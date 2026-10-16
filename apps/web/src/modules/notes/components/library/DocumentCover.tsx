import { FileText, Lock } from '@artha/design-system'

import { useDocumentCover, type UseDocumentCoverOptions } from '../../hooks/useDocumentCover'

/**
 * The cover box of a library card: the server's thumbnail, else a first-page preview drawn on this device, else the file
 * icon. The box keeps its size so the list never jumps; a locked file keeps its lock badge and never gets a preview.
 */
export function DocumentCover({
  doc,
  compact = false,
  mini = false,
  engine,
}: UseDocumentCoverOptions & { /** A 32 x 40 px thumbnail for a table row. */ mini?: boolean }) {
  const { ref, src, onError } = useDocumentCover({ doc, compact, engine })
  return (
    <div
      ref={ref}
      aria-hidden
      data-slot="document-cover"
      className={`relative grid shrink-0 place-items-center overflow-hidden rounded-md border border-border bg-muted shadow-soft ring-1 ring-foreground/5 ring-inset ${mini ? 'h-10 w-8' : compact ? 'h-16 w-12' : 'h-24 w-[4.5rem]'}`}
    >
      {src ? (
        <img src={src} alt="" loading="lazy" onError={onError} className="size-full object-cover" />
      ) : (
        <FileText className={mini ? 'size-4 text-muted-foreground' : 'size-6 text-muted-foreground'} />
      )}
      {doc.status === 'needs_password' ? (
        <span className="absolute right-0.5 bottom-0.5 grid size-5 place-items-center rounded-full bg-card shadow-soft">
          <Lock className="size-3" />
        </span>
      ) : null}
    </div>
  )
}
