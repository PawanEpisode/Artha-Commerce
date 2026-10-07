import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { FilterBar } from './FilterBar'

const tags = [{ id: '3f2b8c1e-5a6d-4e7f-8a9b-0c1d2e3f4a5b', name: 'doubt', color_key: null, count: 2 }]

describe('FilterBar', () => {
  it('shows each active filter as a chip that removes only itself and resets the page', async () => {
    const onChange = vi.fn()
    render(
      <FilterBar
        search={{ tab: 'notes', tag: tags[0]!.id, from: '2026-10-01', cursor: 'abc' }}
        tags={tags}
        onChange={onChange}
      />,
    )
    expect(screen.getByText('Tag: doubt')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remove filter Tag: doubt' }))
    expect(onChange).toHaveBeenCalledWith({ tab: 'notes', from: '2026-10-01' })
  })

  it('clears every filter but keeps the tab', async () => {
    const onChange = vi.fn()
    render(
      <FilterBar search={{ tab: 'notes', from: '2026-10-01', to: '2026-10-09' }} tags={tags} onChange={onChange} />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Clear all' }))
    expect(onChange).toHaveBeenCalledWith({ tab: 'notes' })
  })

  it('shows no chips and no clear button without filters', () => {
    render(<FilterBar search={{}} tags={tags} onChange={() => undefined} />)
    expect(screen.queryByRole('button', { name: 'Clear all' })).toBeNull()
  })

  it('changes the tab and the dates through the URL state', async () => {
    const onChange = vi.fn()
    render(<FilterBar search={{ cursor: 'x' }} tags={tags} onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Notes' }))
    expect(onChange).toHaveBeenLastCalledWith({ cursor: undefined, tab: 'notes' })
  })
})
