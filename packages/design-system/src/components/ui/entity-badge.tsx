import { cva } from 'class-variance-authority'
import * as React from 'react'

import { Bookmark, BookOpen, FileText, GraduationCap, Layers, type LucideIcon } from '../../icons'
import { cn } from '../../lib/utils'

export type EntityKind = 'chapter' | 'topic' | 'paper' | 'subject' | 'level'

const KIND_ICON: Record<EntityKind, LucideIcon> = {
  chapter: BookOpen,
  topic: Bookmark,
  paper: FileText,
  subject: Layers,
  level: GraduationCap,
}

/** Default word for each kind, used when a screen only wants the type shown. */
export const ENTITY_KIND_LABEL: Record<EntityKind, string> = {
  chapter: 'Chapter',
  topic: 'Topic',
  paper: 'Paper',
  subject: 'Subject',
  level: 'Level',
}

const entityBadgeVariants = cva(
  'inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs leading-none font-semibold whitespace-nowrap [&_svg]:size-3.5 [&_svg]:shrink-0',
  {
    variants: {
      kind: {
        chapter: 'border-tag-chapter-border bg-tag-chapter-bg text-tag-chapter-fg',
        topic: 'border-tag-topic-border bg-tag-topic-bg text-tag-topic-fg',
        paper: 'border-tag-paper-border bg-tag-paper-bg text-tag-paper-fg',
        subject: 'border-info-border bg-info-bg text-info-fg',
        level: 'border-border bg-secondary text-secondary-foreground',
      },
      size: { default: '', lg: 'px-3 py-1.5 text-sm [&_svg]:size-4' },
    },
    defaultVariants: { kind: 'chapter', size: 'default' },
  },
)

export interface EntityBadgeProps extends Omit<React.ComponentProps<'span'>, 'children'> {
  kind: EntityKind
  /** Text. Defaults to the kind's name ("Chapter"). */
  children?: React.ReactNode
  /** Show the kind's icon (default) or hide it. Pass a Lucide icon to override. */
  icon?: boolean | LucideIcon
  size?: 'default' | 'lg'
}

/**
 * A coloured label for a syllabus entity: chapters are green, topics amber, papers pink.
 * Colour is never the only signal: the icon and the text name the kind too.
 */
export function EntityBadge({ kind, children, icon = true, size, className, ...props }: EntityBadgeProps) {
  const Icon = typeof icon === 'function' || typeof icon === 'object' ? icon : KIND_ICON[kind]
  return (
    <span
      data-slot="entity-badge"
      data-kind={kind}
      className={cn(entityBadgeVariants({ kind, size }), className)}
      {...props}
    >
      {icon ? <Icon aria-hidden /> : null}
      <span className="truncate">{children ?? ENTITY_KIND_LABEL[kind]}</span>
    </span>
  )
}

/** Alias: some screens read better as "label badge". */
export const LabelBadge = EntityBadge

const RAIL: Record<EntityKind, string> = {
  chapter: 'border-l-tag-chapter',
  topic: 'border-l-tag-topic',
  paper: 'border-l-tag-paper',
  subject: 'border-l-info',
  level: 'border-l-border',
}
const DOT: Record<EntityKind, string> = {
  chapter: 'bg-tag-chapter',
  topic: 'bg-tag-topic',
  paper: 'bg-tag-paper',
  subject: 'bg-info',
  level: 'bg-muted-foreground',
}

/** Small coloured dot for dense lists. Decorative: pair it with text that names the kind. */
export function EntityDot({ kind, className, ...props }: { kind: EntityKind } & React.ComponentProps<'span'>) {
  return (
    <span
      aria-hidden
      data-slot="entity-dot"
      className={cn('inline-block size-2.5 shrink-0 rounded-full', DOT[kind], className)}
      {...props}
    />
  )
}

/** A list row with a coloured left rail so chapters, topics and papers read apart at a glance. */
export function EntityRow({ kind, className, ...props }: { kind: EntityKind } & React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="entity-row"
      data-kind={kind}
      className={cn('rounded-lg border border-l-4 border-border bg-card px-4 py-3', RAIL[kind], className)}
      {...props}
    />
  )
}
