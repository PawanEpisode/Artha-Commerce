import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { InstallGuide } from './InstallGuide'
import { InstallOfferCard } from './InstallOfferCard'

const setup = (kind: 'prompt' | 'ios_steps' | 'mac_safari', busy = false) => {
  const h = { onInstall: vi.fn(), onClose: vi.fn() }
  render(<InstallOfferCard kind={kind} busy={busy} {...h} />)
  return h
}

describe('InstallOfferCard', () => {
  it('is a labelled region with an Install button and Not now where the browser can install in one click', async () => {
    const h = setup('prompt')
    expect(screen.getByRole('region', { name: 'Keep Artha one tap away' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Install Artha/ }))
    expect(h.onInstall).toHaveBeenCalledOnce()
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    expect(h.onClose).toHaveBeenCalledOnce()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('shows the Home Screen steps, and no install button, on iPhone and iPad', async () => {
    const h = setup('ios_steps')
    expect(screen.getByText('Add to Home Screen')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Install Artha/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Got it' }))
    expect(h.onClose).toHaveBeenCalledOnce()
  })

  it('says File, then Add to Dock in Safari on a Mac', () => {
    setup('mac_safari')
    expect(screen.getByText('File')).toBeInTheDocument()
    expect(screen.getByText('Add to Dock')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Install Artha/ })).toBeNull()
  })

  it('uses one copy of the steps: the alerts step shows the same three', () => {
    const steps = ['Open this page in Safari', 'Add to Home Screen', 'Open Artha from your Home Screen']
    const { unmount } = render(<InstallGuide finishing={false} onContinue={() => undefined} />)
    for (const text of steps) expect(screen.getByText(new RegExp(text))).toBeInTheDocument()
    unmount()
    setup('ios_steps')
    for (const text of steps) expect(screen.getByText(new RegExp(text))).toBeInTheDocument()
  })

  it('keeps its buttons tall enough and lets them wrap at 320 px', () => {
    setup('prompt')
    for (const name of [/Install Artha/, 'Not now']) expect(screen.getByRole('button', { name })).toHaveClass('h-auto')
  })
})
