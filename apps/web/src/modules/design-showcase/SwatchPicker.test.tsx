import { type SwatchKey, SwatchPicker } from '@artha/design-system'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

const options = [
  { key: 'y', name: 'Formula or rule' },
  { key: 'g', name: 'Definition' },
  { key: 'b', name: 'Example', disabled: true },
  { key: 'p', name: 'Doubt' },
  { key: 'o', name: 'Exam favourite' },
] as const

describe('SwatchPicker', () => {
  it('is a named radio group whose swatches are named from the legend', () => {
    render(<SwatchPicker label="Highlight colour" options={options} defaultValue="y" />)
    const group = screen.getByRole('radiogroup', { name: 'Highlight colour' })
    expect(group).toBeInTheDocument()
    for (const o of options) expect(screen.getByRole('radio', { name: o.name })).toBeInTheDocument()
  })

  it('gives every swatch its own shape, so colour is not the only signal', () => {
    const { container } = render(
      <SwatchPicker
        label="Pen colour"
        options={['i1', 'i2', 'i3', 'i4', 'i5'].map((key) => ({ key: key as SwatchKey, name: key }))}
      />,
    )
    const shapes = Array.from(container.querySelectorAll('svg[data-shape]')).map((svg) => svg.innerHTML)
    expect(new Set(shapes).size).toBe(5)
  })

  it('marks the selected swatch with a check mark and aria-checked, not just a colour', () => {
    render(<SwatchPicker label="Highlight colour" options={options} defaultValue="g" />)
    const selected = screen.getByRole('radio', { name: 'Definition' })
    expect(selected).toHaveAttribute('aria-checked', 'true')
    expect(selected.querySelector('svg.lucide-check')).not.toBeNull()
    expect(screen.getByRole('radio', { name: 'Doubt' }).querySelector('svg.lucide-check')).toBeNull()
  })

  it('moves the choice with the arrow keys, skipping a disabled swatch', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    render(<SwatchPicker label="Highlight colour" options={options} defaultValue="g" onValueChange={onValueChange} />)
    await user.tab()
    expect(screen.getByRole('radio', { name: 'Definition' })).toHaveFocus()
    await user.keyboard('{ArrowRight>}')
    await waitFor(() => expect(onValueChange).toHaveBeenLastCalledWith('p'))
    await user.keyboard('{/ArrowRight}')
    expect(screen.getByRole('radio', { name: 'Doubt' })).toHaveFocus()
    await user.keyboard('{ArrowLeft>}')
    await waitFor(() => expect(onValueChange).toHaveBeenLastCalledWith('g'))
    await user.keyboard('{/ArrowLeft}')
  })

  it('has a single tab stop (roving tabindex)', async () => {
    const user = userEvent.setup()
    render(
      <>
        <SwatchPicker label="Highlight colour" options={options} defaultValue="y" />
        <button type="button">after</button>
      </>,
    )
    await user.tab()
    await user.tab()
    expect(screen.getByRole('button', { name: 'after' })).toHaveFocus()
  })

  it('calls onSelect on every tap, also on the colour that is already selected', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<SwatchPicker label="Highlight colour" options={options} defaultValue="y" onSelect={onSelect} />)
    await user.click(screen.getByRole('radio', { name: 'Formula or rule' }))
    await user.click(screen.getByRole('radio', { name: 'Formula or rule' }))
    expect(onSelect).toHaveBeenCalledTimes(2)
    expect(onSelect).toHaveBeenLastCalledWith('y')
  })

  it('does not select a disabled swatch', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<SwatchPicker label="Highlight colour" options={options} onSelect={onSelect} />)
    await user.click(screen.getByRole('radio', { name: 'Example' }))
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('keeps a 44 px target for every size and shows names on request', () => {
    const { rerender } = render(<SwatchPicker label="Legend" options={options} size="sm" />)
    for (const radio of screen.getAllByRole('radio')) expect(radio.className).toMatch(/min-h-11/)
    expect(radio0()).toHaveClass('min-w-11')
    rerender(<SwatchPicker label="Legend" options={options} size="lg" showNames />)
    expect(screen.getByRole('radio', { name: 'Exam favourite' })).toHaveTextContent('Exam favourite')
  })
})

function radio0() {
  return screen.getAllByRole('radio')[0]!
}
