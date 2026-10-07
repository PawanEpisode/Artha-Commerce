import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ preview: vi.fn(), confirm: vi.fn() }))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ to, children, ...rest }: { to: string; children: ReactNode }) => (
    <a href={to} {...rest}>
      {children}
    </a>
  ),
}))
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  previewUnsubscribe: state.preview,
  confirmUnsubscribe: state.confirm,
}))

import { ApiError } from '~/lib/api'

import { UnsubscribeContainer } from './UnsubscribeContainer'

const RESULT = { category: 'progress', label: 'Weekly summary', unsubscribed: false }

function show(token: string | undefined = 'tok') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <UnsubscribeContainer token={token} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  state.preview.mockResolvedValue(RESULT)
  state.confirm.mockResolvedValue({ ...RESULT, unsubscribed: true })
})

describe('UnsubscribeContainer', () => {
  it('names the email and waits for one click; opening the link changes nothing', async () => {
    show()
    expect(await screen.findByRole('heading', { name: 'Unsubscribe from the weekly summary?' })).toBeInTheDocument()
    expect(state.preview).toHaveBeenCalledWith('tok')
    expect(state.confirm).not.toHaveBeenCalled()
  })

  it('unsubscribes on the click and says so', async () => {
    const user = userEvent.setup()
    show()
    await user.click(await screen.findByRole('button', { name: 'Unsubscribe' }))
    expect(await screen.findByRole('heading', { name: 'You are unsubscribed' })).toBeInTheDocument()
    expect(state.confirm).toHaveBeenCalledWith('tok')
    expect(screen.getByRole('link', { name: 'Notification settings' })).toHaveAttribute(
      'href',
      '/app/settings/notifications',
    )
  })

  it('explains a link that is not valid, and never calls the server without a token', async () => {
    show('')
    expect(await screen.findByRole('heading', { name: 'This link is not valid' })).toBeInTheDocument()
    expect(state.preview).not.toHaveBeenCalled()
  })

  it('shows a link the server refuses as not valid', async () => {
    state.preview.mockRejectedValue(new ApiError(400, 'bad'))
    show()
    expect(await screen.findByRole('heading', { name: 'This link is not valid' })).toBeInTheDocument()
  })

  it('lets the student try again when the request fails', async () => {
    const user = userEvent.setup()
    state.confirm.mockRejectedValueOnce(new ApiError(503, 'down'))
    show()
    await user.click(await screen.findByRole('button', { name: 'Unsubscribe' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Nothing has changed')
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'You are unsubscribed' })).toBeInTheDocument())
    expect(state.confirm).toHaveBeenCalledTimes(2)
  })
})
