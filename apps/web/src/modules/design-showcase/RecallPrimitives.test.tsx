import { DatePicker, FlipCard, ProgressCounter, RatingButtons } from '@artha/design-system'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { RecallPrimitivesShowcase } from './RecallPrimitivesShowcase'

const previews = { 1: '10 min', 2: '2 d', 3: '5 d', 4: '12 d' } as const

describe('RatingButtons', () => {
  it('shows four words with their interval and key as the accessible name and shortcut', () => {
    render(<RatingButtons onRate={() => {}} previews={previews} />)
    const group = screen.getByRole('group', { name: 'How well did you remember it?' })
    const buttons = screen.getAllByRole('button')
    expect(group).toBeInTheDocument()
    expect(buttons.map((b) => b.getAttribute('aria-label'))).toEqual([
      'Again, next in 10 min',
      'Hard, next in 2 d',
      'Good, next in 5 d',
      'Easy, next in 12 d',
    ])
    expect(buttons.map((b) => b.getAttribute('aria-keyshortcuts'))).toEqual(['1', '2', '3', '4'])
  })

  it('is one tab stop that lands on Good, and arrows move focus without wrapping', async () => {
    const user = userEvent.setup()
    render(<RatingButtons onRate={() => {}} />)
    const [again, hard, good, easy] = screen.getAllByRole('button')
    expect(screen.getAllByRole('button').filter((b) => b.tabIndex === 0)).toEqual([good])
    await user.tab()
    expect(good).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(easy).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(easy).toHaveFocus()
    await user.keyboard('{Home}')
    expect(again).toHaveFocus()
    await user.keyboard('{ArrowLeft}')
    expect(again).toHaveFocus()
    await user.keyboard('{ArrowDown}')
    expect(hard).toHaveFocus()
    expect(hard.tabIndex).toBe(0)
    expect(good.tabIndex).toBe(-1)
  })

  it('answers on Enter, Space and click', async () => {
    const user = userEvent.setup()
    const onRate = vi.fn()
    render(<RatingButtons onRate={onRate} />)
    await user.tab()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')
    await user.click(screen.getByRole('button', { name: 'Again' }))
    expect(onRate.mock.calls.map((c) => c[0])).toEqual([3, 3, 1])
  })

  it('takes 1 to 4 anywhere when shortcuts are on, but not while typing', async () => {
    const user = userEvent.setup()
    const onRate = vi.fn()
    render(
      <>
        <input aria-label="Note" />
        <RatingButtons onRate={onRate} shortcuts />
      </>,
    )
    await user.keyboard('4')
    await user.keyboard('{Control>}1{/Control}')
    await user.click(screen.getByLabelText('Note'))
    await user.keyboard('2')
    expect(onRate.mock.calls.map((c) => c[0])).toEqual([4])
  })

  it('ignores shortcuts and clicks when disabled, and keeps the targets 44 px or larger', async () => {
    const user = userEvent.setup()
    const onRate = vi.fn()
    const { rerender } = render(<RatingButtons onRate={onRate} />)
    for (const b of screen.getAllByRole('button')) {
      expect(b.className).toContain('min-h-14')
      expect(b.className).toContain('min-w-11')
    }
    rerender(<RatingButtons onRate={onRate} shortcuts disabled />)
    await user.keyboard('3')
    await user.click(screen.getAllByRole('button')[0])
    expect(onRate).not.toHaveBeenCalled()
  })
})

function Card({ onSwipe }: { onSwipe?: (d: 'left' | 'right') => void }) {
  const [flipped, setFlipped] = useState(false)
  return (
    <FlipCard
      flipped={flipped}
      onFlip={() => setFlipped(true)}
      swipeEnabled
      onSwipe={onSwipe}
      front={<p>Front text</p>}
      back={<p>Back text</p>}
    />
  )
}

describe('FlipCard', () => {
  it('shows only the question first, announces the change, and moves focus to the answer', async () => {
    const user = userEvent.setup()
    render(<Card />)
    expect(screen.getByRole('status')).toHaveTextContent('Question shown')
    expect(screen.getByText('Back text').closest('[inert]')).not.toBeNull()
    expect(screen.queryByText('Front text')?.closest('[inert]')).toBeNull()
    await user.tab()
    expect(screen.getByRole('button', { name: /Show answer/ })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('status')).toHaveTextContent('Answer shown')
    expect(screen.getByText('Front text').closest('[inert]')).not.toBeNull()
    expect(screen.getByText('Back text').closest('[inert]')).toBeNull()
    expect(screen.queryByRole('button', { name: /Show answer/ })).toBeNull()
    expect(screen.getByText('Back text').parentElement).toHaveFocus()
  })

  it('hides the face that is not showing from the accessibility tree', async () => {
    const user = userEvent.setup()
    render(<Card />)
    expect(screen.getByText('Back text').closest('[aria-hidden="true"]')).not.toBeNull()
    await user.click(screen.getByRole('button', { name: /Show answer/ }))
    expect(screen.getByText('Front text').closest('[aria-hidden="true"]')).not.toBeNull()
    expect(screen.getByText('Back text').closest('[aria-hidden="true"]')).toBeNull()
  })

  it('crossfades with no motion for people who ask for less: the 3D turn is only under motion-safe', () => {
    render(<Card />)
    const turner = screen.getByText('Front text').closest('[data-hidden]')!.parentElement!
    expect(turner.className).toContain('motion-safe:transition-transform')
    expect(turner.className).toContain('motion-reduce:transition-none')
    expect(turner.className).not.toMatch(/(^|\s)transition-transform/)
  })

  it('reports a swipe only after the answer is shown', async () => {
    const user = userEvent.setup()
    const onSwipe = vi.fn()
    render(<Card onSwipe={onSwipe} />)
    const card = screen.getByRole('group', { name: 'Flashcard' })
    const drag = async (from: number, to: number) => {
      const { fireEvent } = await import('@testing-library/react')
      fireEvent.pointerDown(card, { clientX: from, clientY: 0 })
      fireEvent.pointerUp(card, { clientX: to, clientY: 0 })
    }
    await drag(200, 50)
    expect(onSwipe).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /Show answer/ }))
    await drag(200, 50)
    await drag(50, 200)
    await drag(100, 110)
    expect(onSwipe.mock.calls.map((c) => c[0])).toEqual(['left', 'right'])
  })
})

describe('ProgressCounter', () => {
  it('puts the numbers in a polite live region and on the bar as text', () => {
    const { rerender } = render(<ProgressCounter done={12} total={30} label="Cards reviewed" />)
    const live = screen.getByText('12 of 30')
    expect(live).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByRole('progressbar', { name: 'Cards reviewed' })).toHaveAttribute('aria-valuetext', '12 of 30')
    rerender(<ProgressCounter done={13} total={30} label="Cards reviewed" />)
    expect(screen.getByText('13 of 30')).toBeInTheDocument()
    rerender(<ProgressCounter done={0} total={0} label="Cards reviewed" />)
    expect(screen.getByText('No cards')).toBeInTheDocument()
  })
})

describe('DatePicker', () => {
  it('is a labelled native date field with its hint and error described', () => {
    render(
      <DatePicker
        label="Vacation ends on"
        value="2026-10-20"
        onValueChange={() => {}}
        hint="Back the next day."
        error="Pick a later day."
      />,
    )
    const input = screen.getByLabelText('Vacation ends on')
    expect(input).toHaveAttribute('type', 'date')
    expect(input).toHaveValue('2026-10-20')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    const described = input.getAttribute('aria-describedby')!.split(' ')
    const text = described.map((id) => document.getElementById(id)?.textContent)
    expect(text).toEqual(['Pick a later day.', 'Back the next day.'])
    expect(screen.getByRole('alert')).toHaveTextContent('Pick a later day.')
  })

  it('keeps a typed date inside min and max and reports null when cleared', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    const { rerender } = render(
      <DatePicker label="Ends" value={null} onValueChange={onValueChange} min="2026-10-10" max="2026-12-01" />,
    )
    const input = screen.getByLabelText('Ends')
    await user.type(input, '2026-10-01')
    expect(onValueChange).toHaveBeenLastCalledWith('2026-10-10')
    rerender(
      <DatePicker label="Ends" value="2026-11-01" onValueChange={onValueChange} min="2026-10-10" max="2026-12-01" />,
    )
    await user.clear(input)
    expect(onValueChange).toHaveBeenLastCalledWith(null)
  })
})

describe('Recall showcase', () => {
  it('runs a card through flip and answer without a mouse', async () => {
    const user = userEvent.setup()
    render(<RecallPrimitivesShowcase />)
    expect(screen.getByText('12 of 30')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Show answer/ }))
    await user.click(screen.getByRole('button', { name: 'Good, next in 5 d' }))
    expect(screen.getByText('13 of 30')).toBeInTheDocument()
    expect(screen.getByText('Last answer: 3')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Question shown')
  })

  it('has no fixed width that could force sideways scrolling at 320 px', () => {
    const { container } = render(<RecallPrimitivesShowcase />)
    const html = container.innerHTML
    expect(html).not.toMatch(/\bw-\[\d+px\]|\bmin-w-\[\d+px\]|\bmin-w-(?:xs|sm|md|lg)\b/)
    expect(container.querySelector('[class*="max-w-xl"]')?.className).toContain('w-full')
  })
})
