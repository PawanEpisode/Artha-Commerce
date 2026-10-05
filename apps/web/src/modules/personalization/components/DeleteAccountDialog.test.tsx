import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import { DeleteAccountDialog } from './DeleteAccountDialog'

vi.mock('~/modules/auth', () => ({
  ReauthPrompt: ({ onVerified }: { onVerified: () => void }) => <button onClick={onVerified}>mock code step</button>,
}))

function setup(props: Partial<React.ComponentProps<typeof DeleteAccountDialog>> = {}) {
  const onConfirm = vi.fn()
  const onOpenChange = vi.fn()
  render(
    <DeleteAccountDialog
      open
      onOpenChange={onOpenChange}
      pending={false}
      error={null}
      onConfirm={onConfirm}
      {...props}
    />,
  )
  return { onConfirm, onOpenChange }
}

describe('DeleteAccountDialog', () => {
  it('keeps the delete button off until the word is typed', async () => {
    const { onConfirm } = setup()
    const button = screen.getByRole('button', { name: 'Delete everything' })
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/type delete/i), ' delete ')
    expect(button).toBeEnabled()
    await userEvent.click(button)
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('shows the emailed-code step when the server asks for a recent sign-in, then retries', async () => {
    const reauth = new ApiError(401, 'x', { error: { code: 'reauth_required' } })
    const { onConfirm } = setup({ error: reauth })
    expect(screen.queryByLabelText(/type delete/i)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'mock code step' }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('shows other failures inline and keeps the form', () => {
    setup({ error: new ApiError(500, 'x', { error: { code: 'deletion_incomplete' } }) })
    expect(screen.getByRole('alert')).toHaveTextContent('could not finish deleting')
    expect(screen.getByLabelText(/type delete/i)).toBeInTheDocument()
  })

  it('cannot be dismissed while the request is running', async () => {
    const { onOpenChange } = setup({ pending: true })
    await userEvent.keyboard('{Escape}')
    expect(onOpenChange).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /delete everything/i })).toBeDisabled()
  })

  it('closes from Keep my account', async () => {
    const { onOpenChange } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Keep my account' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })
})
