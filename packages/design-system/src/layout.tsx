import type { ComponentProps, ReactNode } from 'react'
import * as React from 'react'

import { cn } from './lib/utils'

/** True inside the signed-in app frame (AppShell). Layout primitives go fluid and compact there. */
export const AppFrameContext = React.createContext(false)
export const useAppFrame = () => React.useContext(AppFrameContext)

/** Drops vertical padding utilities (py-8, sm:py-12, pt-6 ...) so the frame owns the rhythm. Public pages are untouched. */
const VERTICAL_PADDING = /(^|\s)(?:[a-z-]+:)*p[ytb]-(?:\d+|\[[^\]]+\])(?=\s|$)/g
const stripVerticalPadding = (className?: string) => className?.replace(VERTICAL_PADDING, ' ').trim()

/**
 * Page width wrapper. On public pages: centred, max 6xl. Inside the app frame: full width, left aligned, tight gutters,
 * vertical padding owned by the frame. An explicit `max-w-*` still applies (forms and prose stay narrow) but is left aligned.
 */
export function Container({ className, ...props }: ComponentProps<'div'>) {
  const inApp = useAppFrame()
  if (inApp) {
    return <div className={cn('w-full min-w-0 px-4 py-4 md:px-6', stripVerticalPadding(className))} {...props} />
  }
  return <div className={cn('mx-auto w-full max-w-6xl px-5 sm:px-8', className)} {...props} />
}

const PAGE_WIDTH = {
  /** Data pages: tables, boards, dashboards. Uses the whole width. */
  fluid: '',
  /** Forms and settings. */
  form: 'max-w-3xl',
  /** Long reading (notes, explanations). */
  reading: 'max-w-3xl',
} as const

/** The standard app page body: consistent gutters and vertical rhythm. Choose the width by what the page shows. */
export function Page({
  width = 'fluid',
  className,
  ...props
}: ComponentProps<'div'> & { width?: keyof typeof PAGE_WIDTH }) {
  return (
    <div
      data-slot="page"
      className={cn('w-full min-w-0 space-y-4 px-4 py-4 md:px-6', PAGE_WIDTH[width], className)}
      {...props}
    />
  )
}

interface PageHeaderProps extends Omit<ComponentProps<'header'>, 'title'> {
  title: ReactNode
  description?: ReactNode
  /** Right-aligned actions. Keep to one primary button. */
  actions?: ReactNode
  /** Small text above the title (a parent name). */
  eyebrow?: ReactNode
}

/** One compact heading row for every app page: title, a muted line, and the page actions. */
export function PageHeader({ title, description, actions, eyebrow, className, ...props }: PageHeaderProps) {
  return (
    <header
      data-slot="page-header"
      className={cn('flex flex-wrap items-start justify-between gap-x-4 gap-y-2', className)}
      {...props}
    >
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">{eyebrow}</p>
        ) : null}
        <h1 className="truncate text-lg leading-7 font-semibold tracking-tight text-foreground">{title}</h1>
        {description ? <p className="text-[13px] text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  )
}

interface SectionProps extends Omit<ComponentProps<'section'>, 'title'> {
  eyebrow?: string
  title?: ReactNode
  description?: ReactNode
  align?: 'left' | 'center'
}

/** Standard public page section: consistent vertical rhythm and heading block. */
export function Section({
  eyebrow,
  title,
  description,
  align = 'center',
  className,
  children,
  ...props
}: SectionProps) {
  return (
    <section className={cn('py-12 sm:py-20', className)} {...props}>
      <Container>
        {(eyebrow || title || description) && (
          <header className={cn('mb-8 max-w-2xl sm:mb-10', align === 'center' && 'mx-auto text-center')}>
            {eyebrow && <p className="mb-2 text-xs font-semibold tracking-widest text-primary uppercase">{eyebrow}</p>}
            {title && <h2 className="text-2xl font-semibold sm:text-3xl">{title}</h2>}
            {description && <p className="mt-3 text-base text-muted-foreground">{description}</p>}
          </header>
        )}
        {children}
      </Container>
    </section>
  )
}
