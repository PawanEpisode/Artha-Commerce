import { Button, MousePointer2, PenLine, SegmentedControl, SyncChip, UsageBar } from '@artha/design-system'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

describe('SyncChip', () => {
  it.each([
    ['saved', undefined, 'Saved'],
    ['saving', undefined, 'Saving…'],
    ['offline', 3, 'Offline: saved on this device, 3 waiting'],
    ['attention', 2, '2 need your attention'],
  ] as const)('says %s in words inside a polite live region', (state, count, text) => {
    render(<SyncChip state={state} count={count} />)
    const region = screen.getByRole('status')
    expect(region).toHaveAttribute('aria-live', 'polite')
    expect(region).toHaveTextContent(text)
  })
})

describe('UsageBar', () => {
  it('shows the numbers as text and as the meter value text, never colour only', () => {
    render(<UsageBar label="Storage" used={412} limit={500} format={(n) => `${n} MB`} />)
    expect(screen.getAllByText('412 MB of 500 MB').length).toBeGreaterThan(0)
    expect(screen.getByRole('meter', { name: 'Storage' })).toHaveAttribute('aria-valuetext', '412 MB of 500 MB')
  })

  it('adds words when near or at the limit', () => {
    const { rerender } = render(<UsageBar label="Storage" used={460} limit={500} />)
    expect(screen.getByText('Storage almost full')).toBeInTheDocument()
    rerender(<UsageBar label="Storage" used={500} limit={500} fullText="Storage full" />)
    expect(screen.getByText('Storage full')).toBeInTheDocument()
  })
})

describe('SegmentedControl as a tool pill', () => {
  it('keeps the label as the accessible name and moves with arrow keys', async () => {
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    render(
      <SegmentedControl
        label="Tool"
        value="select"
        onValueChange={onValueChange}
        size="lg"
        iconOnlyOnMobile
        options={[
          { value: 'select', label: 'Select', icon: <MousePointer2 aria-hidden /> },
          { value: 'pen', label: 'Pen', icon: <PenLine aria-hidden /> },
        ]}
      />,
    )
    const select = screen.getByRole('radio', { name: 'Select' })
    expect(select).toHaveAttribute('aria-checked', 'true')
    expect(select).toHaveClass('min-w-11', 'h-11')
    await user.click(select)
    await user.keyboard('{ArrowRight>}')
    await waitFor(() => expect(onValueChange).toHaveBeenLastCalledWith('pen'))
    await user.keyboard('{/ArrowRight}')
  })
})

describe('Button touch targets', () => {
  it('reaches 44 px on mobile for sm and icon, and keeps the compact size from sm up', () => {
    render(
      <>
        <Button size="sm">Small</Button>
        <Button size="icon" aria-label="Icon" />
      </>,
    )
    expect(screen.getByRole('button', { name: 'Small' })).toHaveClass('min-h-11', 'sm:min-h-9')
    expect(screen.getByRole('button', { name: 'Icon' })).toHaveClass('size-11', 'sm:size-10')
  })
})
