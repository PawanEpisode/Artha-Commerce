import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { TagEditor } from './TagEditor'

const tags = [
  { id: 'a', name: 'doubt', color_key: null, count: 1 },
  { id: 'b', name: 'formula', color_key: null, count: 3 },
]

describe('TagEditor', () => {
  it('shows the state of each tag as pressed or not', () => {
    render(<TagEditor tags={tags} selectedIds={['b']} onChange={() => undefined} onCreate={async () => undefined} />)
    expect(screen.getByRole('button', { name: 'doubt' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'formula' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('adds and removes a tag from the set', async () => {
    const onChange = vi.fn()
    render(<TagEditor tags={tags} selectedIds={['b']} onChange={onChange} onCreate={async () => undefined} />)
    await userEvent.click(screen.getByRole('button', { name: 'doubt' }))
    expect(onChange).toHaveBeenLastCalledWith(['b', 'a'])
    await userEvent.click(screen.getByRole('button', { name: 'formula' }))
    expect(onChange).toHaveBeenLastCalledWith([])
  })

  it('makes a new tag, selects it and clears the field', async () => {
    const onChange = vi.fn()
    const onCreate = vi.fn(async (name: string) => ({ id: 'n', name, color_key: null, count: 0 }))
    render(<TagEditor tags={tags} selectedIds={[]} onChange={onChange} onCreate={onCreate} />)
    await userEvent.type(screen.getByLabelText('New tag'), 'revise')
    await userEvent.click(screen.getByRole('button', { name: 'Add tag' }))
    expect(onCreate).toHaveBeenCalledWith('revise')
    expect(onChange).toHaveBeenCalledWith(['n'])
    expect(screen.getByLabelText('New tag')).toHaveValue('')
  })

  it('says why a tag cannot be made offline, and says there are no tags yet', () => {
    render(
      <TagEditor
        tags={[]}
        selectedIds={[]}
        onChange={() => undefined}
        onCreate={async () => undefined}
        createDisabledReason="Making a tag needs a connection."
      />,
    )
    expect(screen.getByText('You have no tags yet. Make one below.')).toBeInTheDocument()
    expect(screen.getByLabelText('New tag')).toBeDisabled()
    expect(screen.getByText('Making a tag needs a connection.')).toBeInTheDocument()
  })
})
