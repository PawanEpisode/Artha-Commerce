import { cn, EntityBadge, type EntityBadgeProps, type EntityKind, EntityRow } from '@artha/design-system'
import type { ComponentProps } from 'react'

/**
 * The shared pieces of every syllabus list (public course pages and the signed-in map): papers are pink, chapters
 * green, topics amber. One row anatomy everywhere so titles, badges and progress line up the same way:
 *
 *   [index]  title (two lines at most, full text in the tooltip)        [trailing]
 *            badges ...
 *            progress bar
 */

const INDEX_CLASS: Record<EntityKind, string> = {
  chapter: 'border-tag-chapter-border bg-tag-chapter-bg text-tag-chapter-fg',
  topic: 'border-tag-topic-border bg-tag-topic-bg text-tag-topic-fg',
  paper: 'border-tag-paper-border bg-tag-paper-bg text-tag-paper-fg',
  subject: 'border-info-border bg-info-bg text-info-fg',
  level: 'border-border bg-secondary text-secondary-foreground',
}

/** A list row with the entity's coloured rail. The link inside carries the padding, so the whole row is the target. */
export function EntityListRow({ kind, className, ...props }: { kind: EntityKind } & ComponentProps<'div'>) {
  return (
    <EntityRow
      kind={kind}
      className={cn(
        'p-0 transition-shadow focus-within:ring-[3px] focus-within:ring-ring/40 hover:shadow-(--shadow-soft)',
        className,
      )}
      {...props}
    />
  )
}

/** Classes for the row's link: index, content, trailing value in three aligned columns. */
export const ROW_LINK_CLASS =
  'grid min-h-16 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 rounded-lg p-4 outline-none sm:gap-x-4'

/** The number (or dot) at the start of a row, tinted like the entity. */
export function EntityIndex({ kind, className, ...props }: { kind: EntityKind } & ComponentProps<'span'>) {
  return (
    <span
      aria-hidden
      className={cn(
        'grid size-10 shrink-0 place-items-center rounded-lg border font-display text-base font-bold tabular-nums',
        INDEX_CLASS[kind],
        className,
      )}
      {...props}
    />
  )
}

/** A row title: wraps to two lines, then truncates, with the full text available on hover and focus. */
export function EntityTitle({ className, children, ...props }: ComponentProps<'span'>) {
  return (
    <span
      title={typeof children === 'string' ? children : undefined}
      className={cn('line-clamp-2 block font-semibold break-words', className)}
      {...props}
    >
      {children}
    </span>
  )
}

/** The kind label inside breadcrumbs and headings: truncates long names, keeps the full name in `title`. */
export function EntityCrumb({ kind, children, className, ...props }: EntityBadgeProps) {
  return (
    <EntityBadge
      kind={kind}
      title={typeof children === 'string' ? children : undefined}
      className={cn('max-w-[11rem] sm:max-w-xs', className)}
      {...props}
    >
      {children}
    </EntityBadge>
  )
}

/** Focus ring and shape for a breadcrumb link that wraps an `EntityCrumb`. */
export const CRUMB_LINK_CLASS =
  'inline-flex max-w-full rounded-full outline-none hover:brightness-95 focus-visible:ring-[3px] focus-visible:ring-ring/40'
