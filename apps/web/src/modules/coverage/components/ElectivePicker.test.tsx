import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ElectiveSlot } from '../lib/types'
import { ElectivePicker } from './ElectivePicker'

const slot = (key: string, name: string, chosen: string | null): ElectiveSlot => ({
  key,
  name,
  paper_number: null,
  group_key: null,
  chosen,
  options: [
    { id: `${key}-1`, key: '1', name: `${name} option one` },
    { id: `${key}-2`, key: '2', name: `${name} option two` },
  ],
})

describe('ElectivePicker', () => {
  it('says how many elective papers are left out of the percentages', () => {
    render(
      <ElectivePicker
        slots={[slot('p20', 'Paper 20', null), slot('p21', 'Paper 21', null)]}
        pending={false}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText(/2 elective papers are not chosen yet/)).toBeInTheDocument()
  })

  it('uses the singular for one undecided paper and hides the notice once all are chosen', () => {
    const { rerender } = render(
      <ElectivePicker slots={[slot('p20', 'Paper 20', null)]} pending={false} onChange={vi.fn()} />,
    )
    expect(screen.getByText(/One elective paper is not chosen yet/)).toBeInTheDocument()
    rerender(<ElectivePicker slots={[slot('p20', 'Paper 20', 'p20-1')]} pending={false} onChange={vi.fn()} />)
    expect(screen.queryByText(/not chosen yet/)).not.toBeInTheDocument()
  })

  it('changes one slot at a time', async () => {
    const onChange = vi.fn()
    render(
      <ElectivePicker
        slots={[slot('p20', 'Paper 20', 'p20-1'), slot('p21', 'Paper 21', null)]}
        pending={false}
        onChange={onChange}
      />,
    )
    await userEvent.click(screen.getByRole('radio', { name: /Paper 21 option two/ }))
    expect(onChange).toHaveBeenCalledWith('p21', 'p21-2')
  })

  it('shows a save error and locks the choices while saving', () => {
    render(
      <ElectivePicker
        slots={[slot('p20', 'Paper 20', 'p20-1')]}
        pending
        error="We could not save your elective."
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('We could not save your elective.')
    expect(screen.getByRole('group', { name: /Paper 20/ })).toBeDisabled()
  })
})
