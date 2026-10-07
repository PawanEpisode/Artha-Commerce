import { Skeleton } from '@artha/design-system'

import { TOP_BAR_PX } from './ReaderChrome'

export interface ReaderLoadingProps {
  /** Width over height of the first page when known (from stored page sizes), A4 otherwise. */
  aspect?: number
}

/** Layout-stable placeholder while the document record loads: the bars and one page at the right shape. */
export function ReaderLoading({ aspect = 595 / 842 }: ReaderLoadingProps) {
  return (
    <div role="status" aria-label="Opening the PDF" className="relative h-dvh w-full overflow-hidden bg-muted">
      <div style={{ height: TOP_BAR_PX }} className="flex items-center gap-3 border-b border-border bg-card px-3">
        <Skeleton className="size-9 rounded-lg" />
        <Skeleton className="h-4 w-40 max-w-[50%]" />
      </div>
      <div className="mx-auto mt-2 w-[min(100%-1rem,48rem)]" style={{ aspectRatio: String(aspect) }}>
        <Skeleton className="size-full rounded-none" />
      </div>
      <span className="sr-only">Opening the PDF…</span>
    </div>
  )
}
