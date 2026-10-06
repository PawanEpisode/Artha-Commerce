import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { PermissionView } from '../lib/permissionView'
import { PermissionCard } from './PermissionCard'

function setup(
  view: PermissionView,
  patch: { browser?: 'chrome' | 'safari'; platform?: 'windows' | 'ios' | 'macos' } = {},
) {
  const onEnable = vi.fn()
  const onCheckAgain = vi.fn()
  render(
    <PermissionCard
      view={view}
      browser={patch.browser ?? 'chrome'}
      platform={patch.platform ?? 'windows'}
      busy={false}
      onEnable={onEnable}
      onCheckAgain={onCheckAgain}
    />,
  )
  return { onEnable, onCheckAgain }
}

describe('PermissionCard', () => {
  it('offers the one tap that shows the browser prompt when permission is undecided', async () => {
    const { onEnable } = setup({ kind: 'ready' })
    await userEvent.click(screen.getByRole('button', { name: /Turn on alerts on this device/ }))
    expect(onEnable).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Off')).toBeInTheDocument()
  })

  it('finishes setup when the browser already allows alerts but we have no record', async () => {
    const { onEnable } = setup({ kind: 'granted_no_device' })
    await userEvent.click(screen.getByRole('button', { name: /Set up this device/ }))
    expect(onEnable).toHaveBeenCalledTimes(1)
  })

  it('says alerts are on, with text as well as colour, and offers nothing to press', () => {
    setup({ kind: 'active' })
    expect(screen.getByText('On')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Alerts are on for this device')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('is honest about a block: how to undo it in this browser, and a way to check again, never a dead switch', async () => {
    const { onCheckAgain } = setup({ kind: 'blocked' }, { browser: 'safari', platform: 'macos' })
    expect(screen.getByRole('status')).toHaveTextContent('blocked for this site')
    expect(screen.getByRole('status')).toHaveTextContent('Safari menu')
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Turn on/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Check again/ }))
    expect(onCheckAgain).toHaveBeenCalledTimes(1)
  })

  it('explains the iPhone install steps instead of offering a button that cannot work', () => {
    setup({ kind: 'ios_needs_install' }, { browser: 'safari', platform: 'ios' })
    expect(screen.getByRole('status')).toHaveTextContent('Home Screen app')
    expect(screen.getByText(/Add to Home Screen/)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('names the app for an in-app browser', () => {
    setup({ kind: 'in_app_browser', app: 'Instagram' })
    expect(screen.getByRole('status')).toHaveTextContent('inside Instagram')
    expect(screen.getByRole('status')).toHaveTextContent('Chrome or Safari')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it.each([
    ['unsupported', /cannot show alerts/],
    ['not_configured', /not set up in this version/],
    ['checking', /Checking/],
  ] as const)('says plainly what is true for %s', (kind, text) => {
    setup({ kind })
    expect(screen.getByRole('status')).toHaveTextContent(text)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('has one polite live region and a heading', () => {
    setup({ kind: 'ready' })
    expect(screen.getAllByRole('status')).toHaveLength(1)
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByRole('heading', { level: 2, name: 'This device' })).toBeInTheDocument()
  })
})
