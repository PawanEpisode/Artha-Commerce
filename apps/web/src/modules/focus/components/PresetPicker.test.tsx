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

  it('describes the rhythm in hours and minutes', () => {
    render(<PresetPicker value={presetTimings('classic')} onChange={vi.fn()} />)
    expect(screen.getByText('25 m focus, 5 m break, then a 15 m long break after 4 rounds.')).toBeInTheDocument()
  })

  it('shows hours and minutes boxes for custom timings and reports whole minutes', async () => {
    const onChange = vi.fn()
    const custom = { focus_minutes: 90, short_break_minutes: 5, long_break_minutes: 15, rounds_before_long: 4 }
    render(<PresetPicker value={custom} onChange={onChange} />)
    expect(screen.getByRole('radio', { name: 'Custom' })).toBeChecked()
    const focus = screen.getByRole('group', { name: 'Focus length' })
    expect(focus.querySelector<HTMLInputElement>('input[id$="-h"]')).toHaveValue('1')
    const minutes = focus.querySelector<HTMLInputElement>('input[id$="-m"]') as HTMLInputElement
    expect(minutes).toHaveValue('30')
    await userEvent.clear(minutes)
    await userEvent.type(minutes, '45')
    expect(onChange).toHaveBeenLastCalledWith({ ...custom, focus_minutes: 105 }, 'custom')
  })

  it('does not report a value outside the limits and says why in hours and minutes', async () => {
    const onChange = vi.fn()
    const custom = { focus_minutes: 90, short_break_minutes: 5, long_break_minutes: 15, rounds_before_long: 4 }
    render(<PresetPicker value={custom} onChange={onChange} />)
    const minutes = screen
      .getByRole('group', { name: 'Focus length' })
      .querySelector<HTMLInputElement>('input[id$="-m"]') as HTMLInputElement
    const hours = screen
      .getByRole('group', { name: 'Focus length' })
      .querySelector<HTMLInputElement>('input[id$="-h"]') as HTMLInputElement
    await userEvent.clear(hours)
    await userEvent.clear(minutes)
    onChange.mockClear()
    await userEvent.type(minutes, '2')
    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByText('Focus length must be between 5 minutes and 2 hours.')).toBeInTheDocument()
  })

  it('selects Custom even when the lengths still match a preset', async () => {
    const onChange = vi.fn()
    const classic = presetTimings('classic')
    const { rerender } = render(<PresetPicker value={classic} preset="classic" onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Custom' }))
    expect(onChange).toHaveBeenCalledWith(classic, 'custom')
    expect(screen.getByRole('radio', { name: 'Custom' })).toBeChecked()
    rerender(<PresetPicker value={classic} preset="custom" onChange={onChange} />)
    expect(screen.getByRole('radio', { name: 'Custom' })).toBeChecked()
    expect(screen.getByRole('group', { name: 'Focus length' })).toBeInTheDocument()
  })

  it('treats timings equal to a preset as that preset', () => {
    render(<PresetPicker value={presetTimings('light')} onChange={vi.fn()} />)
    expect(screen.getByRole('radio', { name: 'Light' })).toBeChecked()
  })
})
