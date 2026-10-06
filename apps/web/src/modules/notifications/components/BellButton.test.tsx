import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { BellButton } from './BellButton'

const show = (props: Partial<Parameters<typeof BellButton>[0]> = {}) => {
  const onOpen = vi.fn((event: { preventDefault: () => void }) => event.preventDefault())
  render(<BellButton unread={3} announcement={null} current={false} onOpen={onOpen} {...props} />)
  return { onOpen }
}

describe('BellButton', () => {
  it('is a link to the inbox named with the unread count', () => {
    show()
    const link = screen.getByRole('link', { name: 'Notifications, 3 unread notifications' })
    expect(link).toHaveAttribute('href', '/app/notifications')
    expect(link).not.toHaveAttribute('aria-current')
  })

  it('shows the count as text on a badge hidden from screen readers (the label already says it)', () => {
    show({ unread: 7 })
    const badge = screen.getByText('7')
    expect(badge).toHaveAttribute('aria-hidden', 'true')
  })

  it('caps the badge at 99+ but speaks the real number', () => {
    show({ unread: 240 })
    expect(screen.getByText('99+')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Notifications, 240 unread notifications' })).toBeInTheDocument()
  })

  it('shows no badge at zero and says so', () => {
    show({ unread: 0 })
    expect(screen.queryByText('0')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Notifications, no unread notifications' })).toBeInTheDocument()
  })

  it('is plainly "Notifications" until the first answer', () => {
    show({ unread: null })
    expect(screen.getByRole('link', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('marks the current page', () => {
    show({ current: true })
    expect(screen.getByRole('link', { name: /Notifications/ })).toHaveAttribute('aria-current', 'page')
  })

  it('has a polite live region for count changes', () => {
    show({ announcement: '4 unread notifications' })
    const region = screen.getByRole('status')
    expect(region).toHaveAttribute('aria-live', 'polite')
    expect(region).toHaveTextContent('4 unread notifications')
    expect(region).toHaveClass('sr-only')
  })

  it('opens from the keyboard and the mouse', async () => {
    const user = userEvent.setup()
    const { onOpen } = show()
    const link = screen.getByRole('link', { name: /Notifications/ })
    await user.tab()
    expect(link).toHaveFocus()
    await user.keyboard('{Enter}')
    await user.click(link)
    expect(onOpen).toHaveBeenCalledTimes(2)
  })
})
