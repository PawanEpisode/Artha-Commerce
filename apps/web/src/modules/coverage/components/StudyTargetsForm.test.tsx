import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { DEFAULT_PRESETS } from '../lib/targets'
import { StudyTargetsForm } from './StudyTargetsForm'
import { TargetsImpactDialog } from './TargetsImpactDialog'

const settings = {
  targets: { practice_sets: 1, revisions: 2, mocks: 1 },
  target_presets: [...DEFAULT_PRESETS],
  target_limits: { min: 0, max: 10 },
  targets_confirmed: true,
}

describe('StudyTargetsForm', () => {
  it('starts with Save disabled and shows no preset for custom numbers', () => {
    render(<StudyTargetsForm settings={settings} pending={false} onSave={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Save targets' })).toBeDisabled()
    expect(screen.queryByRole('button', { pressed: true })).not.toBeInTheDocument()
    expect(screen.getByText('Custom plan.')).toBeInTheDocument()
  })

  it('a preset fills the numbers and enables Save with exactly those values', async () => {
    const onSave = vi.fn()
    render(<StudyTargetsForm settings={settings} pending={false} onSave={onSave} />)
    await userEvent.click(screen.getByRole('button', { name: /Intense/ }))
    expect(screen.getByRole('button', { name: /Intense/ })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Save targets' }))
    expect(onSave).toHaveBeenCalledWith({ practice_sets: 3, revisions: 3, mocks: 3 })
  })

  it('a manual change clears the preset highlight and 0 reads as not tracked', async () => {
    render(<StudyTargetsForm settings={settings} pending={false} onSave={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Light/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Decrease Mock tests' }))
    expect(screen.queryByRole('button', { pressed: true })).not.toBeInTheDocument()
    expect(screen.getByText('Not tracked')).toBeInTheDocument()
  })

  it('discard puts the saved numbers back', async () => {
    render(<StudyTargetsForm settings={settings} pending={false} onSave={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Increase Mock tests' }))
    await userEvent.click(screen.getByRole('button', { name: 'Discard changes' }))
    expect(screen.getByRole('button', { name: 'Save targets' })).toBeDisabled()
  })
})

describe('TargetsImpactDialog', () => {
  const props = {
    open: true,
    impact: { chapters_changed: 5, chapters_dropping: 4, chapters_rising: 1 },
    from: { practice_sets: 1, revisions: 1, mocks: 1 },
    to: { practice_sets: 2, revisions: 2, mocks: 2 },
    pending: false,
  }
  it('names how many chapters drop and offers both choices', async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(<TargetsImpactDialog {...props} onConfirm={onConfirm} onCancel={onCancel} />)
    expect(screen.getByText(/4 chapters will show a lower percentage/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Save new targets' }))
    expect(onConfirm).toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Keep current targets' }))
    expect(onCancel).toHaveBeenCalled()
  })
})
