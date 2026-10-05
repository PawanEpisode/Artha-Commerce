import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { RestoreOnLanding } from './RestoreOnLanding'

const go = vi.fn()
vi.mock('~/modules/auth', () => ({ useGoAfterAuth: () => go }))

describe('RestoreOnLanding', () => {
  beforeEach(() => go.mockClear())

  it('is transparent when not arriving from the landing page', () => {
    render(
      <RestoreOnLanding active={false}>
        <p>home</p>
      </RestoreOnLanding>,
    )
    expect(screen.getByText('home')).toBeInTheDocument()
    expect(go).not.toHaveBeenCalled()
  })

  it('shows a skeleton, not the home page, while it decides', () => {
    render(
      <RestoreOnLanding active>
        <p>home</p>
      </RestoreOnLanding>,
    )
    expect(screen.queryByText('home')).toBeNull()
    expect(go).toHaveBeenCalledOnce()
  })
})
