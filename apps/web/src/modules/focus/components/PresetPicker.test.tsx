import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { presetTimings } from '../lib/presets'
import { PresetPicker } from './PresetPicker'

describe('PresetPicker', () => {
  it('switches to a preset and reports its timings', async () => {
    const onChange = vi.fn()
    render(<PresetPicker value={presetTimings('classic')} onChange={onChange} />)
    expect(screen.getByRole('radio', { name: 'Classic' })).toBeChecked()
    await userEvent.click(screen.getByRole('radio', { name: 'Deep' }))
    expect(onChange).toHaveBeenCalledWith(presetTimings('deep'), 'deep')
  })

  it('shows steppers for custom timings and stays within the limits', async () => {
    const onChange = vi.fn()
    const custom = { focus_minutes: 120, short_break_minutes: 1, long_break_minutes: 15, rounds_before_long: 4 }
    render(<PresetPicker value={custom} onChange={onChange} />)
    expect(screen.getByRole('radio', { name: 'Custom' })).toBeChecked()
    expect(screen.getByRole('button', { name: 'Increase Focus minutes' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Decrease Short break minutes' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Decrease Focus minutes' }))
    expect(onChange).toHaveBeenCalledWith({ ...custom, focus_minutes: 115 }, 'custom')
  })

  it('treats timings equal to a preset as that preset', () => {
    render(<PresetPicker value={presetTimings('light')} onChange={vi.fn()} />)
    expect(screen.getByRole('radio', { name: 'Light' })).toBeChecked()
  })
})
