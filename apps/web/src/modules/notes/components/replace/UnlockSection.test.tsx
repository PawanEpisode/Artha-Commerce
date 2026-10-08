import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { UnlockSection } from './UnlockSection'

const base = { statusText: 'This PDF is locked.', working: false, canUnlock: true, online: true }

describe('UnlockSection', () => {
  it('asks for the password, sends it once and empties the field', async () => {
    const onSubmit = vi.fn()
    render(<UnlockSection {...base} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: /Unlock for search/ }))
    const field = screen.getByLabelText('PDF password')
    expect(field).toHaveAttribute('type', 'password')
    await userEvent.type(field, ' s3cret ')
    await userEvent.click(screen.getByRole('button', { name: 'Unlock' }))
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith(' s3cret ') // kept exactly as typed
    expect(screen.queryByLabelText('PDF password')).toBeNull() // and gone from the screen
  })

  it('does not send an empty password and Cancel throws what was typed away', async () => {
    const onSubmit = vi.fn()
    render(<UnlockSection {...base} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: /Unlock for search/ }))
    expect(screen.getByRole('button', { name: 'Unlock' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('PDF password'), 'abc')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await userEvent.click(screen.getByRole('button', { name: /Unlock for search/ }))
    expect(screen.getByLabelText('PDF password')).toHaveValue('')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('shows progress with no button while a try is on its way, and a refusal in an alert', () => {
    render(
      <UnlockSection
        {...base}
        statusText="Reading the PDF with your password…"
        working
        canUnlock={false}
        error="Too many wrong passwords."
        onSubmit={() => undefined}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Reading the PDF')
    expect(screen.getByRole('alert')).toHaveTextContent('Too many')
    expect(screen.queryByRole('button', { name: /Unlock for search/ })).toBeNull()
  })

  it('is disabled offline and renders nothing when there is nothing to say or do', async () => {
    const { container, rerender } = render(<UnlockSection {...base} online={false} onSubmit={() => undefined} />)
    expect(screen.getByRole('button', { name: /Unlock for search/ })).toBeDisabled()
    rerender(<UnlockSection {...base} statusText={null} canUnlock={false} onSubmit={() => undefined} />)
    expect(container).toBeEmptyDOMElement()
  })
})
