import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { NO_FILTERS, toRows } from '../../lib/annotation-filters'
import { DEFAULT_LEGEND, inkOptions, legendOptions } from '../../lib/annotation-legend'
import { DOC, makeMark } from '../../lib/annotation-testing'
import { FILED_LINK } from '../../lib/testing'
import { AnnotationEditSheet } from './AnnotationEditSheet'
import { AnnotationLayer } from './AnnotationLayer'
import { AnnotationList, type AnnotationListProps } from './AnnotationList'
import { MarksLimitNotice } from './MarksLimitNotice'
import { SelectionToolbar } from './SelectionToolbar'
import { ToolOptions, ToolPill } from './ToolPill'

const noop = () => undefined
const anchor = () => new DOMRect(100, 200, 120, 20)

describe('SelectionToolbar', () => {
  const props = {
    open: true,
    onOpenChange: noop,
    anchor,
    options: legendOptions({ ...DEFAULT_LEGEND, g: 'Formula' }),
    color: 'y' as const,
    canCard: false,
    onColor: noop,
    onUnderline: noop,
    onNote: noop,
    onCard: noop,
    onCopy: noop,
  }

  it('offers five colours by the student’s own names, underline, note and copy; Card only when recall exists', () => {
    const { rerender } = render(<SelectionToolbar {...props} />)
    const bar = screen.getByRole('toolbar', { name: 'Mark the selected text' })
    for (const name of ['Important', 'Formula', 'Section or rule', 'Doubt', 'Example'])
      expect(within(bar).getByRole('radio', { name })).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: 'Underline' })).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: /Note/ })).toBeInTheDocument()
    expect(within(bar).queryByRole('button', { name: /card/i })).not.toBeInTheDocument()
    rerender(<SelectionToolbar {...props} canCard cardKindName="Formula" />)
    expect(screen.getByRole('button', { name: 'Make a card: Formula' })).toBeInTheDocument()
  })

  it('saves a highlight with one tap on a colour, and every control is at least 44 px', async () => {
    const onColor = vi.fn()
    render(<SelectionToolbar {...props} onColor={onColor} canCard />)
    await userEvent.click(screen.getByRole('radio', { name: 'Formula' }))
    expect(onColor).toHaveBeenCalledWith('g')
    const bar = screen.getByRole('toolbar')
    for (const button of within(bar).getAllByRole('button')) expect(button.className).toMatch(/min-h-11|size-11/)
    for (const swatch of within(bar).getAllByRole('radio')) expect(swatch.className).toMatch(/min-h-11/)
  })

  it('disables Card with a reason while offline', () => {
    render(<SelectionToolbar {...props} canCard cardDisabledReason="Cards need a connection." />)
    expect(screen.getByRole('button', { name: 'Make a card' })).toBeDisabled()
  })
})

describe('ToolPill and tool options', () => {
  it('collapses to one Mark button while reading, and opens the nine tools as a radio group', async () => {
    const onToolChange = vi.fn()
    const { rerender } = render(<ToolPill tool={undefined} onToolChange={onToolChange} />)
    const mark = screen.getByRole('button', { name: /Mark/ })
    expect(mark.className).toMatch(/min-h-11/)
    await userEvent.click(mark)
    expect(onToolChange).toHaveBeenCalledWith('highlight')
    rerender(<ToolPill tool="highlight" onToolChange={onToolChange} />)
    const group = screen.getByRole('radiogroup', { name: 'Annotation tools' })
    expect(within(group).getAllByRole('radio')).toHaveLength(9)
    expect(within(group).getByRole('radio', { name: 'Highlight' })).toBeChecked()
    await userEvent.click(within(group).getByRole('radio', { name: 'Select' }))
    expect(onToolChange).toHaveBeenLastCalledWith(undefined)
  })

  const options = {
    tool: 'pen' as const,
    markupOptions: legendOptions(),
    markupColor: 'y' as const,
    onMarkupColor: noop,
    inkOptions: inkOptions(),
    inkColor: 'i1' as const,
    onInkColor: noop,
    penWidth: 'medium' as const,
    onPenWidth: noop,
    canUndo: true,
    canRedo: false,
    onUndo: noop,
    onRedo: noop,
    fingerDraws: false,
  }
  it('says how the pen scrolls, with undo and redo as 44 px buttons', () => {
    const { rerender } = render(<ToolOptions {...options} />)
    expect(screen.getByRole('status')).toHaveTextContent('Pen on. Scroll with two fingers.')
    expect(screen.getByRole('status')).toHaveTextContent('one finger scrolls')
    expect(screen.getByRole('button', { name: 'Undo last stroke' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Redo stroke' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Undo last stroke' }).className).toMatch(/size-11/)
    rerender(<ToolOptions {...options} fingerDraws />)
    expect(screen.getByRole('status')).not.toHaveTextContent('one finger scrolls')
  })
})

describe('AnnotationList', () => {
  const marks = [
    makeMark({
      id: 'a',
      page: 14,
      color: 'g',
      quote_exact: 'ITC blocked credits',
      link: FILED_LINK,
      tags: [{ id: 't1', name: 'Doubt', color_key: null }],
    }),
    makeMark({
      id: 'b',
      page: 15,
      kind: 'sticky',
      color: 'y',
      comment: 'z'.repeat(400),
      quote_exact: null,
      geometry: { pt: [0.5, 0.5] },
    }),
  ]
  const legend = { ...DEFAULT_LEGEND, g: 'Formula' }
  const base = (over: Partial<AnnotationListProps> = {}): AnnotationListProps => ({
    rows: toRows(marks, legend),
    total: marks.length,
    status: 'ready',
    onRetry: noop,
    filters: NO_FILTERS,
    onFiltersChange: noop,
    colors: [
      { key: 'y', name: 'Important' },
      { key: 'g', name: 'Formula' },
    ],
    tags: [{ id: 't1', name: 'Doubt', color_key: null }],
    onOpen: noop,
    onEdit: noop,
    onDelete: noop,
    onExpand: noop,
    ...over,
  })

  it('reads each row as the kind, page, colour in words and what it says, and clamps long comments to three lines', () => {
    render(<AnnotationList {...base()} />)
    const rows = screen.getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('Highlight, page 14, green (Formula)')
    expect(rows[0]).toHaveTextContent('ITC blocked credits')
    expect(rows[0]).toHaveTextContent('GST: Input tax credit')
    expect(rows[0]).toHaveTextContent('Doubt')
    expect(within(rows[1] as HTMLElement).getByText('z'.repeat(400)).className).toMatch(/line-clamp-3/)
    expect(within(rows[1] as HTMLElement).getByRole('button', { name: 'Read all' })).toBeInTheDocument()
    expect(within(rows[0] as HTMLElement).queryByRole('button', { name: 'Read all' })).not.toBeInTheDocument()
  })

  it('opens a mark, edits it and deletes it, with Delete on a focused row, all on 44 px targets', async () => {
    const onOpen = vi.fn()
    const onDelete = vi.fn()
    const onEdit = vi.fn()
    render(<AnnotationList {...base({ onOpen, onDelete, onEdit })} />)
    const row = screen.getAllByRole('button', { name: /Highlight, page 14/ })[0] as HTMLElement
    await userEvent.click(row)
    expect(onOpen).toHaveBeenCalledWith('a')
    row.focus()
    await userEvent.keyboard('{Delete}')
    expect(onDelete).toHaveBeenCalledWith('a')
    await userEvent.click(screen.getByRole('button', { name: 'Edit Highlight, page 14' }))
    expect(onEdit).toHaveBeenCalledWith('a')
    for (const name of [/^Edit /, /^Delete /])
      for (const b of screen.getAllByRole('button', { name })) expect(b.className).toMatch(/size-11/)
  })

  it('has a loading state, an error state with a retry, an empty state and a filtered-to-nothing state', async () => {
    const { rerender } = render(<AnnotationList {...base({ rows: [], total: 0, status: 'loading' })} />)
    expect(screen.getByRole('status', { name: 'Loading marks' })).toBeInTheDocument()
    const onRetry = vi.fn()
    rerender(<AnnotationList {...base({ rows: [], total: 0, status: 'error', onRetry })} />)
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalled()
    rerender(<AnnotationList {...base({ rows: [], total: 0 })} />)
    expect(screen.getByText('No marks yet')).toBeInTheDocument()
    const onFiltersChange = vi.fn()
    rerender(<AnnotationList {...base({ rows: [], filters: { ...NO_FILTERS, color: 'g' }, onFiltersChange })} />)
    expect(screen.getByText('No marks match these filters')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(onFiltersChange).toHaveBeenCalledWith(NO_FILTERS)
  })

  it('shows every active filter as a chip that removes itself, and "Mine today" as a pressed toggle', async () => {
    const onFiltersChange = vi.fn()
    render(<AnnotationList {...base({ filters: { ...NO_FILTERS, color: 'g', today: true }, onFiltersChange })} />)
    expect(screen.getByRole('button', { name: 'Mine today' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Colour: Formula')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remove colour filter' }))
    expect(onFiltersChange).toHaveBeenCalledWith({ ...NO_FILTERS, today: true })
  })
})

describe('MarksLimitNotice', () => {
  it('is silent below 95%, quiet at 95% and, at the cap, names the pages with the most ink', async () => {
    const heavy = [
      { page: 7, bytes: 40_000, drawings: 3 },
      { page: 2, bytes: 2_000, drawings: 1 },
    ]
    const { rerender, container } = render(
      <MarksLimitNotice notice="ok" info={{ count: 10, limit: 20_000 }} heavyPages={[]} />,
    )
    expect(container).toBeEmptyDOMElement()
    rerender(<MarksLimitNotice notice="near" info={{ count: 19_100, limit: 20_000 }} heavyPages={heavy} />)
    expect(screen.getByText('This PDF is nearly full of marks.')).toBeInTheDocument()
    expect(screen.queryByText('Pages with the most ink')).not.toBeInTheDocument()
    const onGoToPage = vi.fn()
    rerender(
      <MarksLimitNotice
        notice="blocked"
        info={{ count: 20_000, limit: 20_000 }}
        heavyPages={heavy}
        onGoToPage={onGoToPage}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('has reached its limit of marks')
    expect(screen.getByRole('alert')).toHaveTextContent('20,000 of 20,000 used')
    await userEvent.click(screen.getByRole('button', { name: 'Page 7: 3 drawings, 39 KB' }))
    expect(onGoToPage).toHaveBeenCalledWith(7)
  })
})

describe('AnnotationEditSheet', () => {
  const props = {
    open: true,
    onOpenChange: noop,
    kind: 'highlight' as const,
    heading: 'Highlight, page 14',
    quote: 'ITC blocked credits',
    color: 'g' as const,
    colorOptions: legendOptions({ ...DEFAULT_LEGEND, g: 'Formula' }),
    colorLabel: 'Colour',
    onColor: noop,
    comment: '',
    onCommentChange: noop,
    tags: <div>tags here</div>,
    chapter: <div>chapter here</div>,
    canCard: true,
    hasCard: false,
    onCard: noop,
    onDelete: noop,
  }

  it('names the colours, takes a comment, and has Make card and Delete', async () => {
    const onColor = vi.fn()
    const onCommentChange = vi.fn()
    const onDelete = vi.fn()
    render(<AnnotationEditSheet {...props} onColor={onColor} onCommentChange={onCommentChange} onDelete={onDelete} />)
    const dialog = screen.getByRole('dialog', { name: 'Highlight, page 14' })
    expect(within(dialog).getByRole('radio', { name: 'Formula' })).toBeChecked()
    await userEvent.click(within(dialog).getByRole('radio', { name: 'Doubt' }))
    expect(onColor).toHaveBeenCalledWith('p')
    await userEvent.type(within(dialog).getByLabelText('Comment'), 'x')
    expect(onCommentChange).toHaveBeenCalledWith('x')
    expect(within(dialog).getByRole('button', { name: /Make card/ })).toBeEnabled()
    await userEvent.click(within(dialog).getByRole('button', { name: /Delete/ }))
    expect(onDelete).toHaveBeenCalled()
  })

  it('hides Make card without a recall provider and for kinds without text; a bookmark has a title, not a comment', () => {
    const { rerender } = render(<AnnotationEditSheet {...props} canCard={false} />)
    expect(screen.queryByRole('button', { name: /Make card/ })).not.toBeInTheDocument()
    rerender(<AnnotationEditSheet {...props} kind="bookmark" colorOptions={[]} color={null} />)
    expect(screen.getByLabelText('Title')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Make card/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
  })

  it('explains why Make card is off while offline', () => {
    render(<AnnotationEditSheet {...props} cardDisabledReason="Cards need a connection." />)
    expect(screen.getByRole('button', { name: /Make card/ })).toBeDisabled()
    expect(screen.getByText('Cards need a connection.')).toBeInTheDocument()
  })
})

describe('AnnotationLayer', () => {
  const marks = [
    makeMark({ id: 'h', geometry: { quads: [[0.1, 0.2, 0.5, 0.02]] }, color: 'g' }),
    makeMark({ id: 'p', kind: 'sticky', geometry: { pt: [0.6, 0.6] }, color: 'y', comment: 'a note' }),
  ]
  it('draws highlights under the text from stored geometry at any size, with a shape beside the colour, hidden from assistive technology', () => {
    const { container, rerender } = render(
      <AnnotationLayer layer="under" marks={marks} width={600} height={800} legend={DEFAULT_LEGEND} />,
    )
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true')
    const span = container.querySelector('[data-mark-id="h"]') as HTMLElement
    expect(span).toHaveStyle({ left: '60px', top: '160px', width: '300px', height: '16px' })
    expect(container.querySelector('[data-mark-glyph="h"] svg')).not.toBeNull()
    rerender(<AnnotationLayer layer="under" marks={marks} width={900} height={1200} legend={DEFAULT_LEGEND} />)
    expect(container.querySelector('[data-mark-id="h"]')).toHaveStyle({
      left: '90px',
      top: '240px',
      width: '450px',
      height: '24px',
    })
  })

  it('turns the same stored geometry with the view (90 degrees clockwise swaps the axes)', () => {
    const { container } = render(
      <AnnotationLayer layer="under" marks={marks} width={800} height={600} rotation={90} legend={DEFAULT_LEGEND} />,
    )
    const style = (container.querySelector('[data-mark-id="h"]') as HTMLElement).style
    expect(parseFloat(style.width)).toBeCloseTo(0.02 * 800, 1)
    expect(parseFloat(style.height)).toBeCloseTo(0.5 * 600, 1)
  })

  it('puts the pulse on a found mark, and the ring only animates when motion is allowed', () => {
    const { container } = render(
      <AnnotationLayer
        layer="under"
        marks={marks}
        width={600}
        height={800}
        legend={DEFAULT_LEGEND}
        pulse={{ id: 'h', nonce: 1 }}
      />,
    )
    expect(container.querySelector('[data-mark-id="h"]')?.className).toContain('mark-pulse')
    const css = readFileSync(resolve(process.cwd(), '../../packages/design-system/src/styles.css'), 'utf8')
    const block = css.slice(css.indexOf('.mark-pulse {'))
    expect(block.indexOf('animation')).toBeGreaterThan(block.indexOf('prefers-reduced-motion: no-preference'))
    expect(css).toMatch(/\.mark-pulse \{\s*outline: 3px solid var\(--ring\)/)
  })

  it('draws pins above the text and lets a tap on one select its mark', async () => {
    const onSelect = vi.fn()
    render(
      <AnnotationLayer
        layer="over"
        marks={marks}
        width={600}
        height={800}
        legend={DEFAULT_LEGEND}
        onSelect={onSelect}
      />,
    )
    await userEvent.click(
      screen.getByRole('button', { hidden: true, name: /Note, page 14, yellow \(Important\), a note/ }),
    )
    expect(onSelect).toHaveBeenCalledWith('p')
    expect(DOC).toBeTruthy()
  })
})
