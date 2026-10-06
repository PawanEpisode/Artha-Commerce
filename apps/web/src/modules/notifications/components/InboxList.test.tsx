import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { InboxItem } from '../lib/schemas'
import { InboxList } from './InboxList'

const NOW = Date.parse('2026-10-05T04:35:00Z')
const item = (id: string, over: Partial<InboxItem> = {}): InboxItem => ({
  id,
  category: 'timer',
  category_label: 'Timer alerts',
  title: `Round ${id} done`,
  body: 'Take 5.',
  deep_link: '/app/focus',
  read: false,
  created_at: '2026-10-05T04:30:00Z',
  ...over,
})

function show(items: InboxItem[], props: Partial<Parameters<typeof InboxList>[0]> = {}) {
  const handlers = { onOpen: vi.fn(), onMarkRead: vi.fn(), onLoadMore: vi.fn() }
  render(<InboxList items={items} now={NOW} hasMore={false} loadingMore={false} {...handlers} {...props} />)
  return handlers
}

describe('InboxList', () => {
  it('lists each item with its category, age, title and text', () => {
    show([item('1')])
    const row = screen.getByRole('listitem')
    expect(within(row).getByText('Timer alerts')).toBeInTheDocument()
    expect(within(row).getByText('5 min ago')).toHaveAttribute('datetime', '2026-10-05T04:30:00Z')
    expect(within(row).getByRole('heading', { level: 2, name: 'Round 1 done' })).toBeInTheDocument()
    expect(within(row).getByText('Take 5.')).toBeInTheDocument()
  })

  it('says "New" in words for unread items and "Read" (to screen readers) for read ones, not colour alone', () => {
    show([item('1'), item('2', { read: true })])
    const [unread, read] = screen.getAllByRole('listitem')
    expect(within(unread!).getByText('New')).toBeInTheDocument()
    expect(within(read!).queryByText('New')).not.toBeInTheDocument()
    expect(within(read!).getByText('Read')).toHaveClass('sr-only')
  })

  it('has no heading above level 2 (the page owns the h1)', () => {
    show([item('1'), item('2')])
    expect(screen.queryAllByRole('heading', { level: 1 })).toHaveLength(0)
    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(2)
  })

  it('makes the title a link to the deep link and reports the open', async () => {
    const user = userEvent.setup()
    const { onOpen } = show([item('1', { deep_link: '/app/tracker?d=1' })])
    const link = screen.getByRole('link', { name: 'Round 1 done' })
    expect(link).toHaveAttribute('href', '/app/tracker?d=1')
    await user.click(link)
    expect(onOpen).toHaveBeenCalledTimes(1)
    expect(onOpen.mock.calls[0]?.[0].id).toBe('1')
  })

  it('never renders a link for a path that is not allowed; the title is a button instead', async () => {
    const user = userEvent.setup()
    const { onOpen } = show([item('1', { deep_link: 'https://evil.example/x' })])
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Round 1 done' }))
    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it('offers a named mark-read button on unread items only, and reports it', async () => {
    const user = userEvent.setup()
    const { onMarkRead, onOpen } = show([item('1'), item('2', { read: true })])
    expect(screen.getAllByRole('button', { name: /^Mark ".*" as read$/ })).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Mark "Round 1 done" as read' }))
    expect(onMarkRead).toHaveBeenCalledWith(expect.objectContaining({ id: '1' }))
    expect(onOpen).not.toHaveBeenCalled()
  })

  it('is reachable by keyboard in reading order: title link, then mark read, then the next item', async () => {
    const user = userEvent.setup()
    show([item('1'), item('2')])
    await user.tab()
    expect(screen.getByRole('link', { name: 'Round 1 done' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Mark "Round 1 done" as read' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('link', { name: 'Round 2 done' })).toHaveFocus()
  })

  it('wraps long text instead of widening the page', () => {
    show([item('1', { title: 'x'.repeat(200), body: 'y'.repeat(300) })])
    expect(screen.getByRole('link')).toHaveClass('break-words')
    expect(screen.getByText('y'.repeat(300))).toHaveClass('break-words')
  })

  it('shows "Show older" only when there is more, and busy while loading', async () => {
    const user = userEvent.setup()
    const first = show([item('1')])
    expect(screen.queryByRole('button', { name: 'Show older' })).not.toBeInTheDocument()
    document.body.innerHTML = ''
    const second = show([item('1')], { hasMore: true })
    await user.click(screen.getByRole('button', { name: 'Show older' }))
    expect(second.onLoadMore).toHaveBeenCalledTimes(1)
    expect(first.onLoadMore).not.toHaveBeenCalled()
  })

  it('disables and labels the load button while it loads', () => {
    show([item('1')], { hasMore: true, loadingMore: true })
    const button = screen.getByRole('button', { name: 'Loading…' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
  })
})
