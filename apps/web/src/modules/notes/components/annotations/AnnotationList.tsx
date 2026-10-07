import {
  Alert,
  Badge,
  Button,
  cn,
  EmptyState,
  FilterChip,
  Highlighter,
  Pencil,
  SelectField,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
  SwatchShape,
  Trash2,
  X,
} from '@artha/design-system'
import type { ReactNode } from 'react'

import {
  activeFilterCount,
  type AnnotationFilters,
  type AnnotationRowView,
  NO_FILTERS,
} from '../../lib/annotation-filters'
import type { ColorKey, MarkKind } from '../../lib/annotation-types'
import { KIND_LABEL } from '../../lib/mark-label'
import type { TagRef } from '../../lib/types'
import { TOP_BAR_PX } from '../reader/ReaderChrome'
import { CHIP } from './mark-styles'

export interface ColorChoice {
  key: ColorKey
  name: string
}

export interface AnnotationListProps {
  rows: readonly AnnotationRowView[]
  /** Marks before the filters (to tell "none yet" from "none match"). */
  total: number
  status: 'loading' | 'ready' | 'error'
  onRetry: () => void
  filters: AnnotationFilters
  onFiltersChange: (next: AnnotationFilters) => void
  colors: readonly ColorChoice[]
  tags: readonly TagRef[]
  selectedId?: string | null
  /** Goes to the mark on its page (and pulses it). */
  onOpen: (id: string) => void
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  /** Reads a long comment in full. */
  onExpand: (id: string) => void
  /** Shown above the filters (limit notice). */
  notice?: ReactNode
  onClose?: () => void
}

const KINDS: MarkKind[] = ['highlight', 'underline', 'ink', 'textbox', 'sticky', 'bookmark', 'area']

/** Rows of marks with filters and the four states (loading, error, empty, filtered to nothing). PRD 7.2 and 11. */
export function AnnotationList({
  rows,
  total,
  status,
  onRetry,
  filters,
  onFiltersChange,
  colors,
  tags,
  selectedId,
  onOpen,
  onEdit,
  onDelete,
  onExpand,
  notice,
  onClose,
}: AnnotationListProps) {
  const active = activeFilterCount(filters)
  const set = (patch: Partial<AnnotationFilters>) => onFiltersChange({ ...filters, ...patch })
  return (
    <div data-slot="annotation-list" className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b border-border px-4 py-2">
        <h2 className="min-w-0 flex-1 text-base font-semibold">
          Marks <span className="font-normal text-muted-foreground">({total})</span>
        </h2>
        {onClose ? (
          <Button variant="ghost" size="icon" className="size-11" onClick={onClose} aria-label="Close marks list">
            <X aria-hidden />
          </Button>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 pt-3 pb-28">
        {notice}
        {total > 0 || active > 0 ? (
          <section aria-label="Filter marks" className="space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <SelectField
                aria-label="Filter by colour"
                value={filters.color}
                onValueChange={(color) => set({ color: color as AnnotationFilters['color'] })}
                options={[{ value: '', label: 'Any colour' }, ...colors.map((c) => ({ value: c.key, label: c.name }))]}
              />
              <SelectField
                aria-label="Filter by kind"
                value={filters.kind}
                onValueChange={(kind) => set({ kind: kind as AnnotationFilters['kind'] })}
                options={[{ value: '', label: 'Any kind' }, ...KINDS.map((k) => ({ value: k, label: KIND_LABEL[k] }))]}
              />
              {tags.length > 0 || filters.tag ? (
                <SelectField
                  aria-label="Filter by tag"
                  value={filters.tag}
                  onValueChange={(tag) => set({ tag })}
                  options={[{ value: '', label: 'Any tag' }, ...tags.map((t) => ({ value: t.id, label: t.name }))]}
                />
              ) : null}
              <Button
                variant="outline"
                className="min-h-11 justify-start"
                aria-pressed={filters.today}
                onClick={() => set({ today: !filters.today })}
              >
                Mine today
              </Button>
            </div>
            {active > 0 ? (
              <div className="flex flex-wrap items-center gap-2">
                {filters.color ? (
                  <FilterChip removeLabel="Remove colour filter" onRemove={() => set({ color: '' })}>
                    Colour: {colors.find((c) => c.key === filters.color)?.name ?? filters.color}
                  </FilterChip>
                ) : null}
                {filters.kind ? (
                  <FilterChip removeLabel="Remove kind filter" onRemove={() => set({ kind: '' })}>
                    Kind: {KIND_LABEL[filters.kind]}
                  </FilterChip>
                ) : null}
                {filters.tag ? (
                  <FilterChip removeLabel="Remove tag filter" onRemove={() => set({ tag: '' })}>
                    Tag: {tags.find((t) => t.id === filters.tag)?.name ?? 'unknown'}
                  </FilterChip>
                ) : null}
                {filters.today ? (
                  <FilterChip removeLabel="Remove today filter" onRemove={() => set({ today: false })}>
                    Made today
                  </FilterChip>
                ) : null}
              </div>
            ) : null}
          </section>
        ) : null}

        {status === 'loading' && rows.length === 0 ? (
          <div role="status" aria-label="Loading marks" className="space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-20 w-full rounded-xl" />
            ))}
          </div>
        ) : status === 'error' && rows.length === 0 ? (
          <Alert variant="error">
            <p className="font-semibold">We could not load your marks.</p>
            <Button size="sm" variant="outline" className="mt-2 min-h-11" onClick={onRetry}>
              Try again
            </Button>
          </Alert>
        ) : total === 0 ? (
          <EmptyState
            icon={<Highlighter aria-hidden />}
            title="No marks yet"
            description="Select text and pick a colour, or open Mark to draw and add notes. Your marks show up here."
          />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No marks match these filters"
            description="Try a different colour or kind."
            action={
              <Button variant="outline" className="min-h-11" onClick={() => onFiltersChange(NO_FILTERS)}>
                Clear filters
              </Button>
            }
          />
        ) : (
          <ol aria-label="Marks in reading order" className="space-y-2">
            {rows.map((row) => (
              <li key={row.id}>
                <MarkRow
                  row={row}
                  selected={row.id === selectedId}
                  onOpen={onOpen}
                  onEdit={onEdit}
                  onDelete={onDelete}
                  onExpand={onExpand}
                />
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}

interface MarkRowProps {
  row: AnnotationRowView
  selected: boolean
  onOpen: (id: string) => void
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  onExpand: (id: string) => void
}

/** One mark: where it is, what colour it is in words, what it says (three lines), where it is filed, and what you can do. */
function MarkRow({ row, selected, onOpen, onEdit, onDelete, onExpand }: MarkRowProps) {
  const swatch = row.color ?? null
  return (
    <div
      data-slot="annotation-row"
      data-id={row.id}
      className={cn(
        'rounded-xl border border-border bg-card text-card-foreground',
        selected && 'border-foreground ring-2 ring-foreground/20',
      )}
    >
      <button
        type="button"
        onClick={() => onOpen(row.id)}
        onKeyDown={(e) => {
          if (e.key === 'Delete') {
            e.preventDefault()
            onDelete(row.id)
          }
        }}
        aria-current={selected ? 'true' : undefined}
        aria-keyshortcuts="Delete"
        className="flex min-h-11 w-full items-start gap-3 rounded-t-xl p-3 text-left outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40"
      >
        {swatch ? (
          <span
            aria-hidden
            className={cn('mt-0.5 grid size-6 shrink-0 place-items-center rounded-full p-1', CHIP[swatch])}
          >
            <SwatchShape swatch={swatch} />
          </span>
        ) : (
          <span aria-hidden className="mt-0.5 size-6 shrink-0 rounded-full border border-border bg-muted" />
        )}
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold">
            {row.heading}
            {row.colorText ? <span className="font-normal text-muted-foreground">, {row.colorText}</span> : null}
          </span>
          {row.preview ? <span className="mt-0.5 line-clamp-3 block text-sm break-words">{row.preview}</span> : null}
          {row.chapter || row.tags.length > 0 || row.hasCard || row.unsynced ? (
            <span className="mt-1.5 flex flex-wrap gap-1.5">
              {row.chapter ? <Badge variant="outline">{row.chapter}</Badge> : null}
              {row.tags.map((t) => (
                <Badge key={t.id} variant="default">
                  {t.name}
                </Badge>
              ))}
              {row.hasCard ? <Badge variant="default">Card made</Badge> : null}
              {row.unsynced ? <Badge variant="outline">On this device</Badge> : null}
            </span>
          ) : null}
        </span>
      </button>
      <div className="flex items-center justify-end gap-1 border-t border-border px-2 py-1">
        {row.clamped ? (
          <Button variant="ghost" size="sm" className="mr-auto min-h-11" onClick={() => onExpand(row.id)}>
            Read all
          </Button>
        ) : null}
        <Button
          variant="ghost"
          size="icon"
          className="size-11"
          onClick={() => onEdit(row.id)}
          aria-label={`Edit ${row.heading}`}
        >
          <Pencil aria-hidden />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-11"
          onClick={() => onDelete(row.id)}
          aria-label={`Delete ${row.heading}`}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>
    </div>
  )
}

/** The list on phones: a bottom sheet. */
export function AnnotationListSheet({
  open,
  onOpenChange,
  ...list
}: AnnotationListProps & { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="flex max-h-[85dvh] min-h-[50dvh] flex-col gap-0 p-0 sm:mx-auto sm:max-w-2xl"
      >
        <SheetHeader className="sr-only">
          <SheetTitle>Marks in this PDF</SheetTitle>
          <SheetDescription>Every highlight, drawing and note, in reading order.</SheetDescription>
        </SheetHeader>
        <AnnotationList {...list} onClose={undefined} />
      </SheetContent>
    </Sheet>
  )
}

/** The list on wide screens: a panel docked to the right of the page, so the page stays readable beside it. */
export function AnnotationListAside(list: AnnotationListProps) {
  return (
    <aside
      aria-label="Marks"
      data-slot="annotation-aside"
      style={{ top: TOP_BAR_PX }}
      className="absolute right-0 bottom-0 z-20 hidden w-[22rem] flex-col border-l border-border bg-card text-card-foreground md:flex"
    >
      <AnnotationList {...list} />
    </aside>
  )
}
