import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  flag: true,
  push: vi.fn(),
  track: vi.fn(),
  getInbox: vi.fn(),
  postInboxRead: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  useRouter: () => ({ history: { push: state.push } }),
  Link: ({ to, children, ...rest }: { to: string; children: ReactNode }) => (
    <a href={to} {...rest}>
      {children}
    </a>
  ),
}))
vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => state.flag }))
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  getInbox: state.getInbox,
  postInboxRead: state.postInboxRead,
}))

import { ApiError } from '~/lib/api'

import type { InboxItem, InboxPage } from '../lib/schemas'
import { InboxContainer } from './InboxContainer'

const SENT = Date.parse('2026-10-05T04:30:00Z')
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
const answer = (
  results: InboxItem[],
  unread = results.filter((i) => !i.read).length,
  next: string | null = null,
): InboxPage => ({
  results,
  next_cursor: next,
  unread_count: unread,
})

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <InboxContainer />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.setSystemTime(undefined as never)
  state.flag = true
  state.getInbox.mockResolvedValue(answer([item('1'), item('2', { read: true })]))
  state.postInboxRead.mockResolvedValue(0)
})

/** A server that remembers: after "mark read", later reads show the items read (the page refetches once it settles). */
function serverWith(items: InboxItem[]) {
  const read = new Set<string>()
  state.getInbox.mockImplementation(async () => {
    const rows = items.map((i) => ({ ...i, read: i.read || read.has(i.id) }))
    return answer(rows)
  })
  state.postInboxRead.mockImplementation(async (target: { ids?: string[]; all?: true }) => {
    for (const i of items) if (target.all || target.ids?.includes(i.id)) read.add(i.id)
    return items.filter((i) => !i.read && !read.has(i.id)).length
  })
}

describe('InboxContainer', () => {
  it('has exactly one h1, "Inbox", in every state', async () => {
    show()
    expect(screen.getByRole('heading', { level: 1, name: 'Inbox' })).toBeInTheDocument()
    await screen.findByText('Round 1 done')
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('shows a busy loading state first', () => {
    state.getInbox.mockReturnValue(new Promise(() => undefined))
    show()
    expect(screen.getByText('Loading your notifications…')).toBeInTheDocument()
  })

  it('lists the notifications and says the unread count in a polite live region', async () => {
    show()
    await screen.findByText('Round 1 done')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    const status = screen.getByText('1 unread notification')
    expect(status).toHaveAttribute('aria-live', 'polite')
  })

  it('shows a designed empty state', async () => {
    state.getInbox.mockResolvedValue(answer([]))
    show()
    expect(await screen.findByText('Nothing here yet')).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('shows an error with a working retry', async () => {
    const user = userEvent.setup()
    state.getInbox.mockRejectedValueOnce(new ApiError(500, 'boom'))
    show()
    expect(await screen.findByText(/could not load your notifications/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Round 1 done')).toBeInTheDocument()
  })

  it('says "not available yet" and calls nothing while the flag is off', () => {
    state.flag = false
    show()
    expect(screen.getByText('Notifications are not available yet')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Inbox' })).toBeInTheDocument()
    expect(state.getInbox).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: /Mark all/ })).not.toBeInTheDocument()
  })

  it('says the same when the server answers 403 notifications_disabled', async () => {
    state.getInbox.mockRejectedValue(new ApiError(403, 'off', { error: { code: 'notifications_disabled' } }))
    show()
    expect(await screen.findByText('Notifications are not available yet')).toBeInTheDocument()
  })

  describe('opening an item', () => {
    it('reports inbox_opened, marks it read, and follows its link inside the app', async () => {
      const user = userEvent.setup()
      vi.useFakeTimers({ toFake: ['Date'], now: SENT + 90_000 })
      show()
      await user.click(await screen.findByRole('link', { name: 'Round 1 done' }))
      expect(state.track).toHaveBeenCalledWith('inbox_opened', { category: 'timer', seconds_since_sent: 90 })
      await waitFor(() => expect(state.postInboxRead).toHaveBeenCalledWith({ ids: ['1'] }))
      expect(state.push).toHaveBeenCalledWith('/app/focus')
      vi.useRealTimers()
    })

    it('does not mark an item read twice, but still follows it', async () => {
      const user = userEvent.setup()
      show()
      await user.click(await screen.findByRole('link', { name: 'Round 2 done' }))
      expect(state.postInboxRead).not.toHaveBeenCalled()
      expect(state.push).toHaveBeenCalledWith('/app/focus')
      expect(state.track).toHaveBeenCalledWith('inbox_opened', expect.objectContaining({ category: 'timer' }))
    })

    it('never sends text, ids or links to analytics', async () => {
      const user = userEvent.setup()
      show()
      await user.click(await screen.findByRole('link', { name: 'Round 1 done' }))
      const [, props] = state.track.mock.calls[0] as [string, Record<string, unknown>]
      expect(Object.keys(props).sort()).toEqual(['category', 'seconds_since_sent'])
    })

    it('marks read but leaves a ctrl-click to the browser', async () => {
      const user = userEvent.setup()
      show()
      const link = await screen.findByRole('link', { name: 'Round 1 done' })
      await user.keyboard('{Control>}')
      await user.click(link)
      await waitFor(() => expect(state.postInboxRead).toHaveBeenCalledWith({ ids: ['1'] }))
      expect(state.push).not.toHaveBeenCalled()
    })

    it('marks read but does not navigate when the link is not an allowed path', async () => {
      const user = userEvent.setup()
      state.getInbox.mockResolvedValue(answer([item('1', { deep_link: 'https://evil.example/x' })]))
      show()
      await user.click(await screen.findByRole('button', { name: 'Round 1 done' }))
      await waitFor(() => expect(state.postInboxRead).toHaveBeenCalledWith({ ids: ['1'] }))
      expect(state.push).not.toHaveBeenCalled()
    })

    it('does not navigate to a protocol-relative link either', async () => {
      const user = userEvent.setup()
      state.getInbox.mockResolvedValue(answer([item('1', { deep_link: '//evil.example' })]))
      show()
      await user.click(await screen.findByRole('button', { name: 'Round 1 done' }))
      expect(state.push).not.toHaveBeenCalled()
    })
  })

  describe('marking read', () => {
    it('marks one item read from its button and updates the list and the count at once', async () => {
      const user = userEvent.setup()
      serverWith([item('1'), item('2', { read: true })])
      show()
      await user.click(await screen.findByRole('button', { name: 'Mark "Round 1 done" as read' }))
      expect(state.postInboxRead).toHaveBeenCalledWith({ ids: ['1'] })
      await waitFor(() => expect(screen.getByText('No unread notifications')).toBeInTheDocument())
      expect(screen.queryByRole('button', { name: /^Mark ".*" as read$/ })).not.toBeInTheDocument()
      expect(state.push).not.toHaveBeenCalled()
    })

    it('marks all read, and disables the button when nothing is unread', async () => {
      const user = userEvent.setup()
      serverWith([item('1'), item('3')])
      show()
      const all = await screen.findByRole('button', { name: 'Mark all as read' })
      await user.click(all)
      expect(state.postInboxRead).toHaveBeenCalledWith({ all: true })
      await waitFor(() => expect(screen.getByRole('button', { name: 'Mark all as read' })).toBeDisabled())
    })

    it('disables mark all while everything is read', async () => {
      state.getInbox.mockResolvedValue(answer([item('2', { read: true })]))
      show()
      expect(await screen.findByRole('button', { name: 'Mark all as read' })).toBeDisabled()
    })

    it('says so and puts the item back when marking fails', async () => {
      const user = userEvent.setup()
      state.postInboxRead.mockRejectedValue(new ApiError(500, 'boom'))
      show()
      await user.click(await screen.findByRole('button', { name: 'Mark "Round 1 done" as read' }))
      expect(await screen.findByText(/could not mark that as read/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Mark "Round 1 done" as read' })).toBeInTheDocument()
    })
  })

  it('loads older items with the cursor and shows them after the first page', async () => {
    const user = userEvent.setup()
    state.getInbox
      .mockResolvedValueOnce(answer([item('1')], 1, 'cur-1'))
      .mockResolvedValue(answer([item('9', { read: true })], 1))
    show()
    await user.click(await screen.findByRole('button', { name: 'Show older' }))
    expect(await screen.findByText('Round 9 done')).toBeInTheDocument()
    expect(state.getInbox).toHaveBeenLastCalledWith({ cursor: 'cur-1', limit: 20 })
    const titles = within(screen.getByRole('list')).getAllByRole('heading', { level: 2 })
    expect(titles.map((h) => h.textContent)).toEqual(['Round 1 done', 'Round 9 done'])
    expect(screen.queryByRole('button', { name: 'Show older' })).not.toBeInTheDocument()
  })

  it('links to the notification settings', async () => {
    show()
    expect(await screen.findByRole('link', { name: /Settings/ })).toHaveAttribute('href', '/app/settings/notifications')
  })
})
