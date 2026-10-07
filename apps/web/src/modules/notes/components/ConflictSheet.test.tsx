import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ConflictSheet } from './ConflictSheet'

const theirs = { title: 'GST', body_md: 'line one\nTHEIR line\nline three', updated_at: '2026-10-05T10:30:00Z' }
const mine = { title: 'GST', body: 'line one\nMY line\nline three' }

describe('ConflictSheet', () => {
  it('names the two versions and marks the differing lines with words', () => {
    render(
      <ConflictSheet
        open
        onOpenChange={() => undefined}
        theirs={theirs}
        mine={mine}
        busy={false}
        onResolve={() => undefined}
        deviceLabel="Your phone"
      />,
    )
    expect(screen.getByRole('dialog')).toHaveTextContent('This note changed somewhere else')
    expect(screen.getByRole('dialog')).toHaveTextContent('Your phone saved a version')
    const diff = screen.getByRole('region', { name: 'Differences between the two versions' })
    expect(within(diff).getByText('THEIR line').parentElement).toHaveTextContent('Theirs')
    expect(within(diff).getByText('MY line').parentElement).toHaveTextContent('Yours')
  })

  it('resolves with mine, theirs or both', async () => {
    const onResolve = vi.fn()
    render(
      <ConflictSheet
        open
        onOpenChange={() => undefined}
        theirs={theirs}
        mine={mine}
        busy={false}
        onResolve={onResolve}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Keep mine' }))
    await userEvent.click(screen.getByRole('button', { name: 'Keep theirs' }))
    await userEvent.click(screen.getByRole('button', { name: 'Keep both' }))
    expect(onResolve.mock.calls.map((c) => c[0])).toEqual(['mine', 'theirs', 'both'])
  })

  it('disables the choices while one is being saved', () => {
    render(
      <ConflictSheet
        open
        onOpenChange={() => undefined}
        theirs={theirs}
        mine={mine}
        busy
        onResolve={() => undefined}
      />,
    )
    for (const name of ['Keep mine', 'Keep theirs', 'Keep both'])
      expect(screen.getByRole('button', { name })).toBeDisabled()
  })

  it('mentions a changed title', () => {
    render(
      <ConflictSheet
        open
        onOpenChange={() => undefined}
        theirs={{ ...theirs, title: 'Old' }}
        mine={{ ...mine, title: 'New' }}
        busy={false}
        onResolve={() => undefined}
      />,
    )
    expect(screen.getByText(/theirs is/)).toHaveTextContent('theirs is “Old”, yours is “New”')
  })

  it('can say "mark" for a conflict on a comment of a highlight, drawing or pin (the same sheet, the same three choices)', () => {
    render(
      <ConflictSheet
        open
        onOpenChange={() => undefined}
        noun="mark"
        theirs={{ title: '', body_md: 'Section 17(5) blocks cars', updated_at: '2026-10-05T10:30:00Z' }}
        mine={{ title: '', body: 'Section 17(5) blocks cars and boats' }}
        deviceLabel="Pixel 7"
        busy={false}
        onResolve={() => undefined}
      />,
    )
    expect(screen.getByRole('dialog')).toHaveTextContent('This mark changed somewhere else')
    expect(screen.getByRole('dialog')).toHaveTextContent('Pixel 7 saved a version')
  })
})
