import { ArrowLeft, Button, cn } from '@artha/design-system'
import type { ReactNode } from 'react'

/** Height of the top bar, CSS pixels: the reading area keeps this much room above the first page. */
export const TOP_BAR_PX = 56

export interface ReaderChromeProps {
  /** Both bars shown. When false they slide away and cannot take focus (any key or tap in the middle brings them back). */
  visible: boolean
  title: string
  subtitle?: string
  onBack: () => void
  backLabel?: string
  /** Search, outline, page tone, zoom and menu buttons (each 44 px). */
  actions: ReactNode
  /** The page scrubber, the tool row and the sync and marks slots. */
  bottom: ReactNode
  /** Floating notices and panels that sit under the top bar (search panel, notices). */
  notices?: ReactNode
  /** A panel docked to the right from `md` up. The reading area makes room while the panel has `data-slot="annotation-aside"`. */
  side?: ReactNode
  /** The reading area, behind the bars. */
  children: ReactNode
  className?: string
}

/**
 * The reader's frame: the reading area fills the screen and the top and bottom bars float over it. The container hides
 * them after a second of scrolling down and shows them on a tap in the middle or on scrolling up; with reduced motion
 * they appear and disappear without sliding. Hidden bars are `inert`, so nothing invisible can be tabbed to.
 */
export function ReaderChrome({
  visible,
  title,
  subtitle,
  onBack,
  backLabel = 'Back to library',
  actions,
  bottom,
  notices,
  side,
  children,
  className,
}: ReaderChromeProps) {
  return (
    <div className={cn('group/chrome relative h-dvh w-full overflow-hidden bg-background text-foreground', className)}>
      <header
        inert={!visible}
        style={{ height: TOP_BAR_PX }}
        className={cn(
          'absolute inset-x-0 top-0 z-30 flex items-center gap-1 border-b border-border bg-card/95 px-2 text-card-foreground shadow-soft backdrop-blur-sm transition-transform duration-200 motion-reduce:transition-none',
          visible ? 'translate-y-0' : '-translate-y-full',
        )}
      >
        <Button variant="ghost" size="icon" className="size-11 shrink-0" onClick={onBack} aria-label={backLabel}>
          <ArrowLeft aria-hidden />
        </Button>
        <div className="min-w-0 flex-1 px-1">
          <h1 className="truncate text-sm leading-tight font-semibold">{title}</h1>
          {subtitle ? <p className="truncate text-xs text-muted-foreground">{subtitle}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-0.5">{actions}</div>
      </header>
      <div className="h-full md:group-has-[[data-slot=annotation-aside]]/chrome:pr-[22rem]">{children}</div>
      {side}
      {notices ? (
        <div
          className="absolute inset-x-0 z-20 mx-auto flex w-full max-w-xl flex-col gap-2 px-3"
          style={{ top: visible ? TOP_BAR_PX + 8 : 8 }}
        >
          {notices}
        </div>
      ) : null}
      <footer
        inert={!visible}
        className={cn(
          'absolute inset-x-0 bottom-0 z-30 border-t border-border bg-card/95 pb-[env(safe-area-inset-bottom)] text-card-foreground shadow-soft backdrop-blur-sm transition-transform duration-200 motion-reduce:transition-none',
          visible ? 'translate-y-0' : 'translate-y-full',
        )}
      >
        {bottom}
      </footer>
    </div>
  )
}
