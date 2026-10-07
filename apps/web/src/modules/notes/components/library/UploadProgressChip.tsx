import type { UploadItem } from '../../lib/upload-manager'
import { UploadRow, type UploadRowActions } from './UploadRow'

interface UploadProgressChipProps extends UploadRowActions {
  items: readonly UploadItem[]
  /** The sentence for screen readers (the latest `announceChange`). */
  announcement: string
  /** The library shows the same rows inline, so the chip steps aside there. */
  hidden?: boolean
}

const MAX_VISIBLE = 3

/**
 * The compact upload progress that stays in the app layout while the student moves around (FR-F03-02). Hidden when nothing
 * is uploading. A polite live region announces the start, each quarter, each phase change and the end, not every byte.
 */
export function UploadProgressChip({ items, announcement, hidden, ...actions }: UploadProgressChipProps) {
  return (
    <>
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
      {items.length > 0 && !hidden ? (
        <section
          aria-label="Uploads"
          data-slot="upload-chip"
          className="fixed inset-x-4 bottom-20 z-[60] mx-auto flex max-w-sm flex-col gap-2 sm:right-auto sm:bottom-4 sm:left-4 sm:mx-0 sm:w-[22rem]"
        >
          {items.slice(0, MAX_VISIBLE).map((item) => (
            <UploadRow key={item.id} item={item} compact {...actions} />
          ))}
          {items.length > MAX_VISIBLE ? (
            <p className="rounded-lg bg-card px-3 py-2 text-center text-xs text-muted-foreground shadow-soft">
              and {items.length - MAX_VISIBLE} more
            </p>
          ) : null}
        </section>
      ) : null}
    </>
  )
}
