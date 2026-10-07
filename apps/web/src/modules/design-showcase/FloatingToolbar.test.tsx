import { FloatingToolbar, FloatingToolbarButton, FloatingToolbarSeparator, SwatchPicker } from '@artha/design-system'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useRef, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

const rect = new DOMRect(100, 200, 120, 20)

function Harness({ initialOpen = true, onOpenChange }: { initialOpen?: boolean; onOpenChange?: (o: boolean) => void }) {
  const [open, setOpen] = useState(initialOpen)
  const returnRef = useRef<HTMLButtonElement>(null)
  return (
    <>
      <button ref={returnRef} type="button" onClick={() => setOpen(true)}>
        selection
      </button>
      <FloatingToolbar
        open={open}
        onOpenChange={(o) => {
          setOpen(o)
          onOpenChange?.(o)
        }}
        anchor={rect}
        label="Selection tools"
        returnFocusRef={returnRef}
      >
        <FloatingToolbarButton aria-label="Highlight">H</FloatingToolbarButton>
        <FloatingToolbarButton aria-label="Underline">U</FloatingToolbarButton>
        <FloatingToolbarSeparator />
        <FloatingToolbarButton aria-label="Note">N</FloatingToolbarButton>
      </FloatingToolbar>
    </>
  )
}

describe('FloatingToolbar', () => {
  it('is absent from the page until open', () => {
    render(<Harness initialOpen={false} />)
    expect(screen.queryByRole('toolbar')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Highlight' })).toBeNull()
  })

  it('is a labelled toolbar and does not take focus when it opens', async () => {
    render(<Harness />)
    expect(await screen.findByRole('toolbar', { name: 'Selection tools' })).toBeInTheDocument()
    expect(screen.getByRole('toolbar')).toHaveAttribute('aria-orientation', 'horizontal')
    expect(document.body).toHaveFocus()
  })

  it('moves between its buttons with arrow keys, Home and End, with one tab stop', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await screen.findByRole('toolbar')
    const first = screen.getByRole('button', { name: 'Highlight' })
    first.focus()
    await user.keyboard('{ArrowRight}')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Underline' })).toHaveFocus())
    await user.keyboard('{ArrowRight}')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Note' })).toHaveFocus())
    await user.keyboard('{Home}')
    await waitFor(() => expect(first).toHaveFocus())
    await user.keyboard('{End}')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Note' })).toHaveFocus())
    const tabbable = screen.getAllByRole('button').filter((b) => b.getAttribute('tabindex') === '0')
    expect(tabbable.filter((b) => b.closest('[role=toolbar]'))).toHaveLength(1)
  })

  it('closes on Escape and returns focus to the element it was given', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    render(<Harness onOpenChange={onOpenChange} />)
    const button = await screen.findByRole('button', { name: 'Underline' })
    button.focus()
    await user.keyboard('{Escape}')
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(screen.queryByRole('toolbar')).toBeNull()
    expect(screen.getByRole('button', { name: 'selection' })).toHaveFocus()
  })

  it('does not trap focus: Tab off the last control leaves, closes and returns focus', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const first = await screen.findByRole('button', { name: 'Highlight' })
    first.focus()
    await user.tab() // one tab stop (roving), so this is already the edge
    expect(screen.queryByRole('toolbar')).toBeNull()
    expect(screen.getByRole('button', { name: 'selection' })).toHaveFocus()
  })

  it('tabs on to a swatch picker inside it before leaving', async () => {
    const user = userEvent.setup()
    render(
      <FloatingToolbar open onOpenChange={() => undefined} anchor={rect} label="Tools">
        <FloatingToolbarButton aria-label="Highlight">H</FloatingToolbarButton>
        <SwatchPicker label="Colour" options={[{ key: 'y', name: 'Rule' }]} />
      </FloatingToolbar>,
    )
    const first = await screen.findByRole('button', { name: 'Highlight' })
    first.focus()
    await user.tab()
    expect(screen.getByRole('radio', { name: 'Rule' })).toHaveFocus()
  })

  it('moves focus into the toolbar with its shortcut', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await screen.findByRole('toolbar')
    await user.keyboard('{F10}')
    expect(screen.getByRole('toolbar')).toContainElement(document.activeElement as HTMLElement)
  })

  it('holds other controls such as a swatch picker', async () => {
    render(
      <FloatingToolbar open onOpenChange={() => undefined} anchor={rect} label="Tools">
        <SwatchPicker label="Colour" options={[{ key: 'y', name: 'Rule' }]} />
      </FloatingToolbar>,
    )
    expect(await screen.findByRole('radiogroup', { name: 'Colour' })).toBeInTheDocument()
  })
})
