import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ flag: true, pathname: '/app', push: vi.fn(), getInbox: vi.fn() }))

vi.mock('@tanstack/react-router', () => ({
  useRouter: () => ({ history: { push: state.push } }),
  useLocation: ({ select }: { select: (l: { pathname: string }) => unknown }) => select({ pathname: state.pathname }),
}))
vi.mock('~/modules/observability', () => ({ track: vi.fn(), useFeatureFlag: () => state.flag }))
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  getInbox: state.getInbox,
}))

import { ApiError } from '~/lib/api'

import { BellContainer } from './BellContainer'

const answer = (unread: number) => ({ results: [], next_cursor: null, unread_count: unread })

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <BellContainer />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  state.flag = true
  state.pathname = '/app'
  state.getInbox.mockResolvedValue(answer(2))
})

describe('BellContainer', () => {
  it('shows the bell with the count once the API answers', async () => {
    show()
    expect(screen.getByRole('link', { name: 'Notifications' })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Notifications, 2 unread notifications' })).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('stays silent on the first answer', async () => {
    show()
    await screen.findByRole('link', { name: /2 unread/ })
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
  })

  it('renders nothing while the notifications_ui flag is off, and never calls the API', async () => {
    state.flag = false
    const { container } = show()
    await act(async () => undefined)
    expect(container).toBeEmptyDOMElement()
    expect(state.getInbox).not.toHaveBeenCalled()
  })

  it('renders nothing when the server says notifications are disabled', async () => {
    state.getInbox.mockRejectedValue(new ApiError(403, 'off', { error: { code: 'notifications_disabled' } }))
    const { container } = show()
    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })

  it('keeps the bell, without a count, when the API fails for another reason', async () => {
    state.getInbox.mockRejectedValue(new ApiError(500, 'boom'))
    show()
    await waitFor(() => expect(state.getInbox).toHaveBeenCalled())
    expect(screen.getByRole('link', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('opens the inbox in the app on a plain click', async () => {
    const user = userEvent.setup()
    show()
    await user.click(screen.getByRole('link', { name: /Notifications/ }))
    expect(state.push).toHaveBeenCalledWith('/app/notifications')
  })

  it('leaves a ctrl-click to the browser (a new tab)', async () => {
    const user = userEvent.setup()
    show()
    await user.keyboard('{Control>}')
    await user.click(screen.getByRole('link', { name: /Notifications/ }))
    expect(state.push).not.toHaveBeenCalled()
  })

  it('marks the link current on the inbox page, with or without a trailing slash', () => {
    state.pathname = '/app/notifications/'
    show()
    expect(screen.getByRole('link', { name: /Notifications/ })).toHaveAttribute('aria-current', 'page')
  })

  it('announces a changed count politely, after a push refresh', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <BellContainer />
      </QueryClientProvider>,
    )
    await screen.findByRole('link', { name: /2 unread/ })
    state.getInbox.mockResolvedValue(answer(3))
    await act(() => client.invalidateQueries({ queryKey: ['notifications', 'inbox'] }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('3 unread notifications'))
  })
})
