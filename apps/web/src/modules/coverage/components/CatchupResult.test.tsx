import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const flag = vi.hoisted(() => ({ on: false }))
vi.mock('~/modules/observability', () => ({ useFeatureFlag: () => flag.on }))
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to, search }: { children: React.ReactNode; to: string; search?: object }) => (
    <a href={to} data-search={JSON.stringify(search ?? {})}>
      {children}
    </a>
  ),
}))

import { CatchupResult } from './CatchupResult'

describe('CatchupResult', () => {
  beforeEach(() => {
    flag.on = false
  })

  it('goes to the syllabus map when Today is off', () => {
    render(<CatchupResult levelName="CA Inter" percent={20} startWith={null} />)
    expect(screen.getByRole('link', { name: /open my syllabus map/i })).toHaveAttribute('href', '/app/syllabus')
    expect(screen.queryByRole('link', { name: /today's plan/i })).toBeNull()
  })

  it('offers the first plan reveal when Today is on', () => {
    flag.on = true
    render(<CatchupResult levelName="CA Inter" percent={20} startWith={null} />)
    const link = screen.getByRole('link', { name: /see today's plan/i })
    expect(link).toHaveAttribute('href', '/app/today')
    expect(link.getAttribute('data-search')).toContain('onboarding')
  })
})
