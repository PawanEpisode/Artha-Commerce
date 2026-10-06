import { render } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const register = vi.hoisted(() => vi.fn())
vi.mock('../hooks/useServiceWorkerRegistration', () => ({ useServiceWorkerRegistration: register }))

import { resetLandingState, takeLandingId } from '../lib/landing'
import { NotificationsBoot } from './NotificationsBoot'

beforeEach(() => {
  resetLandingState()
  register.mockClear()
  window.history.replaceState(null, '', '/')
})

describe('NotificationsBoot', () => {
  it('renders nothing, and starts the service worker registration', () => {
    const { container } = render(<NotificationsBoot />)
    expect(container).toBeEmptyDOMElement()
    expect(register).toHaveBeenCalledTimes(1)
  })

  it('remembers a notification id from the address the app was opened with', () => {
    window.history.replaceState(null, '', '/app/focus?n=abc123')
    render(<NotificationsBoot />)
    expect(takeLandingId()).toBe('abc123')
  })

  it('remembers nothing when the address has none', () => {
    render(<NotificationsBoot />)
    expect(takeLandingId()).toBeNull()
  })
})
