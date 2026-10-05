import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { ChapterSearch } from './ChapterSearch'

function Harness({ total = 12, matching = 12 }: { total?: number; matching?: number }) {
  const [value, setValue] = useState('')
  return <ChapterSearch value={value} onChange={setValue} shown={value ? matching : total} total={total} />
}

describe('ChapterSearch', () => {
  it('is a labelled search box', () => {
    render(<Harness />)
    expect(screen.getByRole('searchbox', { name: 'Find a chapter' })).toBeInTheDocument()
  })

  it('shows the match count only once something is typed', async () => {
    render(<Harness total={12} matching={1} />)
    expect(screen.queryByText(/match/)).not.toBeInTheDocument()
    await userEvent.type(screen.getByRole('searchbox'), 'tax')
    expect(screen.getByText('1 chapter of 12 match')).toBeInTheDocument()
  })

  it('ignores a query that is only spaces', async () => {
    render(<Harness />)
    await userEvent.type(screen.getByRole('searchbox'), '   ')
    expect(screen.queryByText(/match/)).not.toBeInTheDocument()
  })
})
