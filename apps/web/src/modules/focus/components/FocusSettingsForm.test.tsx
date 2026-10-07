import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { FocusSettings } from '../lib/types'
import { FocusSettingsForm } from './FocusSettingsForm'

const settings: FocusSettings = {
  preset: 'classic',
  focus_minutes: 25,
  short_break_minutes: 5,
  long_break_minutes: 15,
  rounds_before_long: 4,
  auto_start_breaks: true,
  auto_start_focus: false,
  overtime_enabled: true,
  sound_enabled: true,
  volume: 70,
  notifications_enabled: false,
  keep_awake: true,
  keep_awake_in_breaks: false,
  popout_on_start: false,
  popout_size: 'pill',
  popout_prompt_seen: false,
  intro_seen: true,
}

function setup(
  over: Partial<FocusSettings> = {},
  props: { wakeLockSupported?: boolean; showKeepAwake?: boolean; showPopOut?: boolean; popoutSupported?: boolean } = {},
) {
  const onChange = vi.fn()
  render(
    <FocusSettingsForm
      value={{ ...settings, ...over }}
      onChange={onChange}
      onTimingsChange={vi.fn()}
      onPreview={vi.fn()}
      permission="default"
      busy={false}
      {...props}
    />,
  )
  return onChange
}

describe('FocusSettingsForm keep-awake switches (FR-K5)', () => {
  it('shows both switches with the defaults: focus on, breaks off', () => {
    setup()
    expect(screen.getByRole('switch', { name: 'Keep the screen on during focus rounds' })).toBeChecked()
    expect(screen.getByRole('switch', { name: 'Also keep it on during breaks' })).not.toBeChecked()
  })

  it('saves each change straight away', async () => {
    const onChange = setup()
    await userEvent.click(screen.getByRole('switch', { name: 'Also keep it on during breaks' }))
    expect(onChange).toHaveBeenCalledWith({ keep_awake_in_breaks: true })
    await userEvent.click(screen.getByRole('switch', { name: 'Keep the screen on during focus rounds' }))
    expect(onChange).toHaveBeenCalledWith({ keep_awake: false })
  })

  it('disables the break switch while the main switch is off', () => {
    setup({ keep_awake: false })
    expect(screen.getByRole('switch', { name: 'Also keep it on during breaks' })).toBeDisabled()
  })

  it('explains an unsupported browser without hiding the setting', () => {
    setup({}, { wakeLockSupported: false })
    expect(screen.getByText(/cannot keep the screen on/i)).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Keep the screen on during focus rounds' })).toBeEnabled()
  })

  it('hides the section when the keep_awake flag is off', () => {
    setup({}, { showKeepAwake: false })
    expect(screen.queryByRole('heading', { name: 'Screen' })).not.toBeInTheDocument()
  })

  it('has one heading for the section, reachable by name', () => {
    setup()
    expect(screen.getByRole('heading', { name: 'Screen', level: 2 })).toBeInTheDocument()
  })
})

describe('FocusSettingsForm pop-out section (X-01 P4)', () => {
  it('shows the switch off and the size on Pill by default', () => {
    setup()
    expect(screen.getByRole('heading', { name: 'Pop-out timer', level: 2 })).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Pop out when I start a round' })).not.toBeChecked()
    expect(screen.getByRole('radio', { name: 'Pill' })).toBeChecked()
  })

  it('saves each change straight away', async () => {
    const onChange = setup()
    await userEvent.click(screen.getByRole('switch', { name: 'Pop out when I start a round' }))
    expect(onChange).toHaveBeenCalledWith({ popout_on_start: true })
    await userEvent.click(screen.getByRole('radio', { name: 'Card' }))
    expect(onChange).toHaveBeenCalledWith({ popout_size: 'card' })
  })

  it('reflects the saved size', () => {
    setup({ popout_size: 'card', popout_on_start: true })
    expect(screen.getByRole('radio', { name: 'Card' })).toBeChecked()
    expect(screen.getByRole('switch', { name: 'Pop out when I start a round' })).toBeChecked()
  })

  it('hides the section when the floating_timer flag is off', () => {
    setup({}, { showPopOut: false })
    expect(screen.queryByRole('heading', { name: 'Pop-out timer' })).not.toBeInTheDocument()
  })

  it('says plainly that a browser without Picture-in-Picture opens a window that is not on top', () => {
    setup({}, { popoutSupported: false })
    expect(screen.getByText(/does not stay on top/i)).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Pop out when I start a round' })).toBeEnabled()
  })

  it('keeps quiet about it in a browser that supports it', () => {
    setup()
    expect(screen.queryByText(/does not stay on top/i)).not.toBeInTheDocument()
  })
})
