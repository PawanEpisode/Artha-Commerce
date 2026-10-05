import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { NameForm } from './NameForm'

describe('NameForm', () => {
  it('keeps Save off until the name changes, then saves the cleaned name', async () => {
    const onSave = vi.fn()
    render(<NameForm value="Aarav" pending={false} onSave={onSave} />)
    const save = screen.getByRole('button', { name: 'Save name' })
    expect(save).toBeDisabled()
    const field = screen.getByLabelText('Your name')
    await userEvent.clear(field)
    await userEvent.type(field, '  Aarav   Mehta ')
    await userEvent.click(save)
    expect(onSave).toHaveBeenCalledWith('Aarav Mehta')
  })

  it('shows the rule inline for an empty name and does not save', async () => {
    const onSave = vi.fn()
    render(<NameForm value="Aarav" pending={false} onSave={onSave} />)
    await userEvent.clear(screen.getByLabelText('Your name'))
    await userEvent.tab()
    expect(screen.getByRole('alert')).toHaveTextContent('Enter your name.')
    expect(screen.getByRole('button', { name: 'Save name' })).toBeDisabled()
    expect(onSave).not.toHaveBeenCalled()
  })

  it('shows a server message and is disabled while offline', () => {
    render(
      <NameForm value="Aarav" pending={false} serverError="Use 60 characters or fewer." disabled onSave={vi.fn()} />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Use 60 characters or fewer.')
    expect(screen.getByLabelText('Your name')).toBeDisabled()
  })
})
