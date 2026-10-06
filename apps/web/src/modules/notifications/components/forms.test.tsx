import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { NotificationCategory, NotificationDevice } from '../lib/schemas'
import { CategoryGrid } from './CategoryGrid'
import { DeviceList } from './DeviceList'
import { NudgeForm } from './NudgeForm'
import { QuietHoursForm } from './QuietHoursForm'
import { TimeField } from './TimeField'
import { TimeZoneField } from './TimeZoneField'

afterEach(() => vi.useRealTimers())

describe('CategoryGrid', () => {
  const categories: NotificationCategory[] = [
    {
      key: 'timer',
      label: 'Timer alerts',
      description: 'Rounds and breaks.',
      channels: { push: true, email: false, inbox: true },
    },
    {
      key: 'progress',
      label: 'Weekly summary',
      description: 'A weekly look.',
      channels: { push: false, email: true, inbox: true },
    },
  ]

  it('names every switch by its category and channel, and shows its state', () => {
    render(<CategoryGrid categories={categories} onChange={vi.fn()} />)
    expect(screen.getByRole('switch', { name: 'Timer alerts, Push' })).toBeChecked()
    expect(screen.getByRole('switch', { name: 'Timer alerts, Email' })).not.toBeChecked()
    expect(screen.getByRole('switch', { name: 'Weekly summary, Email' })).toBeChecked()
    expect(screen.getAllByRole('switch')).toHaveLength(6)
    expect(screen.getByRole('group', { name: 'Timer alerts' })).toBeInTheDocument()
  })

  it('reports one change per tap, and toggles from the visible label too', async () => {
    const onChange = vi.fn()
    render(<CategoryGrid categories={categories} onChange={onChange} />)
    await userEvent.click(screen.getByRole('switch', { name: 'Timer alerts, Push' }))
    expect(onChange).toHaveBeenLastCalledWith({ category: 'timer', channel: 'push', enabled: false })
    await userEvent.click(screen.getAllByText('Email')[0] as HTMLElement)
    expect(onChange).toHaveBeenLastCalledWith({ category: 'timer', channel: 'email', enabled: true })
    expect(onChange).toHaveBeenCalledTimes(2)
  })

  it('works from the keyboard', async () => {
    const onChange = vi.fn()
    render(<CategoryGrid categories={categories} onChange={onChange} />)
    screen.getByRole('switch', { name: 'Timer alerts, Push' }).focus()
    await userEvent.keyboard(' ')
    expect(onChange).toHaveBeenCalledWith({ category: 'timer', channel: 'push', enabled: false })
  })
})

describe('TimeField', () => {
  it('commits on blur, only for a valid time', async () => {
    const onCommit = vi.fn()
    render(<TimeField id="t" label="Time" value="09:30" onValueChange={vi.fn()} onCommit={onCommit} />)
    const input = screen.getByLabelText('Time')
    input.focus()
    await userEvent.tab()
    expect(onCommit).toHaveBeenCalledWith('09:30')
  })

  it('does not commit an empty or invalid time', async () => {
    const onCommit = vi.fn()
    render(<TimeField id="t" label="Time" value="" onValueChange={vi.fn()} onCommit={onCommit} />)
    screen.getByLabelText('Time').focus()
    await userEvent.tab()
    expect(onCommit).not.toHaveBeenCalled()
  })

  it('commits a moment after the last change, for pickers that never blur', () => {
    vi.useFakeTimers()
    const onCommit = vi.fn()
    render(<TimeField id="t" label="Time" value="09:30" onValueChange={vi.fn()} onCommit={onCommit} />)
    fireEvent.change(screen.getByLabelText('Time'), { target: { value: '10:15' } })
    expect(onCommit).not.toHaveBeenCalled()
    act(() => void vi.advanceTimersByTime(900))
    expect(onCommit).toHaveBeenCalledWith('10:15')
  })

  it('shows its error with the field', () => {
    render(
      <TimeField
        id="t"
        label="Time"
        value="09:30"
        error="Pick another time."
        onValueChange={vi.fn()}
        onCommit={vi.fn()}
      />,
    )
    expect(screen.getByLabelText('Time')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent('Pick another time.')
  })
})

describe('QuietHoursForm', () => {
  it('describes the window in words, including across midnight', () => {
    render(<QuietHoursForm enabled start="22:00" end="07:00" onChange={vi.fn()} />)
    expect(screen.getByText('Quiet from 10:00 pm until 7:00 am the next morning.')).toBeInTheDocument()
  })

  it('hides the times when switched off', () => {
    render(<QuietHoursForm enabled={false} start="22:00" end="07:00" onChange={vi.fn()} />)
    expect(screen.queryByLabelText('Quiet from')).not.toBeInTheDocument()
  })

  it('saves the switch alone', async () => {
    const onChange = vi.fn()
    render(<QuietHoursForm enabled start="22:00" end="07:00" onChange={onChange} />)
    await userEvent.click(screen.getByRole('switch', { name: 'Quiet hours' }))
    expect(onChange).toHaveBeenCalledWith({ quiet_enabled: false })
  })

  it('does not save equal start and end, and says why', async () => {
    const onChange = vi.fn()
    render(<QuietHoursForm enabled start="22:00" end="07:00" onChange={onChange} />)
    const end = screen.getByLabelText('Quiet until')
    fireEvent.change(end, { target: { value: '22:00' } })
    fireEvent.blur(end)
    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('Start and end must be different times.')
  })

  it('does not save a time that did not change', () => {
    const onChange = vi.fn()
    render(<QuietHoursForm enabled start="22:00" end="07:00" onChange={onChange} />)
    fireEvent.blur(screen.getByLabelText('Quiet from'))
    expect(onChange).not.toHaveBeenCalled()
  })
})

describe('NudgeForm', () => {
  it('saves the switch, the tone and the time separately', async () => {
    const onChange = vi.fn()
    render(<NudgeForm enabled time="10:00" tone="calm" onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Driven' }))
    expect(onChange).toHaveBeenLastCalledWith({ nudge_tone: 'driven' })
    await userEvent.click(screen.getByRole('switch', { name: 'Daily nudge' }))
    expect(onChange).toHaveBeenLastCalledWith({ nudge_enabled: false })
    const time = screen.getByLabelText('Around this time')
    fireEvent.change(time, { target: { value: '09:00' } })
    fireEvent.blur(time)
    expect(onChange).toHaveBeenLastCalledWith({ nudge_time: '09:00' })
  })

  it('offers all three tones, with the current one chosen', () => {
    render(<NudgeForm enabled time="10:00" tone="celebratory" onChange={vi.fn()} />)
    expect(screen.getAllByRole('radio').map((r) => r.textContent)).toEqual(['Calm', 'Driven', 'Celebratory'])
    expect(screen.getByRole('radio', { name: 'Celebratory' })).toBeChecked()
  })
})

describe('TimeZoneField', () => {
  const options = [
    { value: 'Asia/Kolkata', label: 'Asia / Kolkata' },
    { value: 'Asia/Dubai', label: 'Asia / Dubai' },
  ]

  it('proposes the browser zone and applies it on request', async () => {
    const onChange = vi.fn()
    render(<TimeZoneField value="Asia/Kolkata" options={options} proposal="Asia/Dubai" onChange={onChange} />)
    expect(screen.getByText(/Your browser says you are in/)).toHaveTextContent('Asia/Dubai')
    await userEvent.click(screen.getByRole('button', { name: 'Use this time zone' }))
    expect(onChange).toHaveBeenCalledWith('Asia/Dubai')
  })

  it('shows no proposal when the zones agree', () => {
    render(<TimeZoneField value="Asia/Kolkata" options={options} proposal={null} onChange={vi.fn()} />)
    expect(screen.queryByText(/Your browser says/)).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Your time zone' })).toBeInTheDocument()
  })
})

describe('DeviceList', () => {
  const devices: NotificationDevice[] = [
    {
      id: 'a',
      label: 'Chrome on Android',
      platform: 'android',
      browser: 'chrome',
      display_mode: 'browser',
      last_seen_at: '2026-10-06T08:00:00Z',
    },
    {
      id: 'b',
      label: 'Artha app on iOS',
      platform: 'ios',
      browser: 'safari',
      display_mode: 'standalone',
      last_seen_at: null,
    },
  ]
  const now = new Date('2026-10-06T12:00:00Z')

  it('says "No device yet" with a way forward', () => {
    render(<DeviceList devices={[]} currentId={null} removingId={null} onRemove={vi.fn()} />)
    expect(screen.getByText(/No device yet/)).toBeInTheDocument()
  })

  it('marks this device in words and names each Remove button for its device', async () => {
    const onRemove = vi.fn()
    render(<DeviceList devices={devices} currentId="a" removingId={null} onRemove={onRemove} now={now} />)
    expect(screen.getByText('This device')).toBeInTheDocument()
    expect(screen.getByText('2 of 10 devices')).toBeInTheDocument()
    expect(screen.getByText(/Installed app/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remove Artha app on iOS' }))
    expect(onRemove).toHaveBeenCalledWith(devices[1])
  })

  it('shows progress on the device being removed only', () => {
    render(<DeviceList devices={devices} currentId={null} removingId="b" onRemove={vi.fn()} now={now} />)
    expect(screen.getByRole('button', { name: 'Remove Artha app on iOS' })).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('button', { name: 'Remove Chrome on Android' })).not.toHaveAttribute('aria-busy', 'true')
  })
})
