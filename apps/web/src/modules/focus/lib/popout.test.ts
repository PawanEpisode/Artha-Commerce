import { describe, expect, it } from 'vitest'

import {
  advanceRound,
  END_CONFIRM_CONTROLS,
  nextStartBody,
  phaseTarget,
  POPOUT_SIZES,
  popoutAlive,
  type PopoutContext,
  type PopoutControl,
  type PopoutPresence,
  popoutView,
  PRESENCE_WINDOW_SECONDS,
  presenceAfterTap,
  presenceFlags,
  promptEligible,
  rememberContext,
  shouldOpenOnStart,
  visibleControls,
} from './popout'
import type { FocusSettings, FocusTimer, IdleInfo } from './types'

const START = Date.parse('2026-10-05T04:30:00Z')
const at = (seconds: number) => START + seconds * 1000
const iso = (seconds: number) => new Date(at(seconds)).toISOString()

const timer = (patch: Partial<FocusTimer> = {}): FocusTimer => ({
  phase: 'focus',
  status: 'running',
  round_number: 2,
  rounds_before_long: 4,
  cycle_id: 'c',
  preset: 'classic',
  planned_seconds: 1500,
  elapsed_seconds: 0,
  remaining_seconds: 1500,
  extension_count: 0,
  overtime_enabled: true,
  overtime_seconds: 0,
  can_extend: true,
  started_at: iso(0),
  paused_at: null,
  paused_total_seconds: 0,
  pause_count: 0,
  ends_at: iso(1500),
  last_seen_at: iso(0),
  away_pending: false,
  auto_start_breaks: true,
  auto_start_focus: false,
  subject_id: 's1',
  chapter_id: 'c1',
  activity_type: 'other',
  client_id: 'k',
  version: 1,
  ...patch,
})

const last: PopoutContext = { subject_id: 's1', chapter_id: 'c1', activity_type: 'other' }
const idle = (patch: Partial<IdleInfo> = {}): IdleInfo => ({
  next_phase: 'focus',
  next_round: 1,
  rounds_before_long: 4,
  cycle_id: null,
  ...patch,
})
const ids = (controls: readonly PopoutControl[]) => controls.map((c) => c.id)
const view = (t: FocusTimer | null, seconds: number, i: IdleInfo | null = null, ctx: PopoutContext | null = last) =>
  popoutView(t, i, null, at(seconds), ctx)

describe('popoutView: a focus round before the target', () => {
  it('shows the clock, "Round n of m" and Pause, +5 with the extensions left, End', () => {
    const v = view(timer(), 12 * 60 + 48)
    expect(v).toMatchObject({ kind: 'focus', clock: '12:12', caption: 'Round 2 of 4', ended: false, ring: true })
    expect(v.spoken).toBe('12 minutes 12 seconds left')
    expect(v.controls.map((c) => [c.id, c.label, c.pill])).toEqual([
      ['pause', 'Pause', true],
      ['extend', '+5 (3 left)', false],
      ['end', 'End', false],
    ])
  })

  it('counts the extensions down and disables +5 when none are left', () => {
    expect(view(timer({ extension_count: 2 }), 10).controls[1]?.label).toBe('+5 (1 left)')
    const none = view(timer({ extension_count: 3, can_extend: false }), 10).controls[1]
    expect(none).toMatchObject({ label: '+5', disabled: true })
  })

  it('puts only Pause in the pill and everything in the card', () => {
    const v = view(timer(), 10)
    expect(ids(visibleControls(v.controls, 'pill', true))).toEqual(['pause'])
    expect(ids(visibleControls(v.controls, 'card', true))).toEqual(['pause', 'extend', 'end'])
  })
})

describe('popoutView: past the target (overtime)', () => {
  const over = (patch: Partial<FocusTimer> = {}) => view(timer(patch), 1500 + 5)

  it('shows +mm:ss in the phase-end state with Start break, then Pause; no +5 and no End', () => {
    const v = over()
    expect(v).toMatchObject({ kind: 'overtime', clock: '+00:05', caption: 'Target reached', ended: true, percent: 100 })
    expect(v.controls.map((c) => [c.id, c.label, c.primary, c.pill])).toEqual([
      ['stop_save', 'Start break', true, true],
      ['pause', 'Pause', false, false],
    ])
  })

  it('reads "Stop and save" when breaks do not start by themselves', () => {
    expect(over({ auto_start_breaks: false }).controls[0]).toMatchObject({ id: 'stop_save', label: 'Stop and save' })
  })

  it('offers Resume and then the stop button when paused past the target', () => {
    const v = over({ status: 'paused', paused_at: iso(1503) })
    expect(ids(v.controls)).toEqual(['resume', 'stop_save'])
    expect(ids(visibleControls(v.controls, 'pill', true))).toEqual(['resume'])
  })

  it('is just a finished round, with no overtime, when overtime is off', () => {
    expect(over({ overtime_enabled: false }).kind).toBe('focus')
  })
})

describe('popoutView: paused, away, breaks', () => {
  it('paused: Resume in the pill, End in the card', () => {
    const v = view(timer({ status: 'paused', paused_at: iso(600) }), 900)
    expect(v).toMatchObject({ kind: 'paused', paused: true, clock: '15:00', caption: 'Round 2 of 4 · paused' })
    expect(v.spoken).toBe('15 minutes left, paused')
    expect(ids(visibleControls(v.controls, 'pill', true))).toEqual(['resume'])
    expect(ids(visibleControls(v.controls, 'card', true))).toEqual(['resume', 'end'])
  })

  it('away: asks "Count it?" with Yes and No in both sizes', () => {
    const v = view(timer({ status: 'away' }), 1600)
    expect(v).toMatchObject({ kind: 'away', clock: 'Count it?', ended: true, ring: false })
    expect(v.message).toBe('The round ended while you were away. Did you study through it?')
    expect(ids(visibleControls(v.controls, 'pill', true))).toEqual(['claim_yes', 'claim_no'])
  })

  it.each([
    ['short_break', 'Short break'],
    ['long_break', 'Long break'],
  ] as const)('%s: ring, the break name and Skip break', (phase, label) => {
    const v = view(timer({ phase, planned_seconds: 300 }), 60)
    expect(v).toMatchObject({ kind: 'break', label, clock: '04:00', caption: 'After round 2' })
    expect(ids(visibleControls(v.controls, 'pill', true))).toEqual(['skip_break'])
  })
})

describe('popoutView: nothing runs', () => {
  it('a break is waiting: "Round done" and Start break, or Start long break', () => {
    const short = view(null, 0, idle({ next_phase: 'short_break', next_round: 2 }))
    expect(short).toMatchObject({ kind: 'waiting', clock: 'Round done', ended: true, ring: false })
    expect(short.controls).toMatchObject([{ id: 'start_next', label: 'Start break', primary: true, pill: true }])
    expect(view(null, 0, idle({ next_phase: 'long_break', next_round: 4 })).controls[0]?.label).toBe('Start long break')
  })

  it('the next round is waiting: "Break over" and Start round N', () => {
    const v = view(null, 0, idle({ next_round: 3 }))
    expect(v).toMatchObject({ kind: 'waiting', clock: 'Break over' })
    expect(v.controls[0]).toMatchObject({ id: 'start_next', label: 'Start round 3' })
  })

  it('with no remembered subject the only way on is Back to Artha', () => {
    expect(ids(view(null, 0, idle({ next_phase: 'short_break', next_round: 2 }), null).controls)).toEqual(['back'])
    expect(ids(view(null, 0, idle({ next_round: 3 }), null).controls)).toEqual(['back'])
  })

  it('nothing due: "No timer running" and Back to Artha, with or without a remembered subject', () => {
    for (const ctx of [last, null]) {
      const v = view(null, 0, idle(), ctx)
      expect(v).toMatchObject({ kind: 'idle', clock: 'No timer running', ended: false })
      expect(ids(v.controls)).toEqual(['back'])
    }
    expect(view(null, 0, null).kind).toBe('idle')
  })

  it('drops Back to Artha where the browser cannot focus the tab', () => {
    expect(visibleControls(view(null, 0, idle()).controls, 'pill', false)).toEqual([])
  })
})

describe('popoutView: stopwatch', () => {
  it('shows the elapsed time and Pause while it runs, Resume while it is paused', () => {
    const running = popoutView(null, null, { paused: false, seconds: 3725 }, at(0), null)
    expect(running).toMatchObject({ kind: 'stopwatch', clock: '01:02:05', caption: 'Elapsed', ring: false })
    expect(running.spoken).toBe('Elapsed 1 hour 2 minutes')
    expect(ids(running.controls)).toEqual(['pause'])
    const paused = popoutView(null, null, { paused: true, seconds: 60 }, at(0), null)
    expect(ids(paused.controls)).toEqual(['resume'])
    expect(paused.paused).toBe(true)
  })

  it('wins over a timer, because only one can run', () => {
    expect(popoutView(timer(), null, { paused: false, seconds: 5 }, at(10), last).kind).toBe('stopwatch')
  })
})

describe('window helpers', () => {
  it('has the two sizes the PRD names', () => {
    expect(POPOUT_SIZES).toEqual({ pill: [320, 156], card: [320, 300] })
  })

  it('confirms End with Save and end, Discard and an icon-only Keep going', () => {
    expect(END_CONFIRM_CONTROLS.map((c) => [c.id, c.iconOnly])).toEqual([
      ['save_end', false],
      ['discard', false],
      ['keep_going', true],
    ])
  })

  it('remembers the context of the last round and keeps the same object while it is unchanged', () => {
    const a = rememberContext(null, timer())
    expect(a).toEqual(last)
    expect(rememberContext(a, timer({ round_number: 3 }))).toBe(a)
    expect(rememberContext(a, timer({ chapter_id: 'c2' }))).toMatchObject({ chapter_id: 'c2' })
    expect(rememberContext(a, null)).toBe(a)
  })

  it('builds the request for the next phase from the settings and the remembered context', () => {
    const classic = { preset: 'classic' } as FocusSettings
    expect(nextStartBody(idle({ next_round: 3 }), last, classic)).toEqual({
      preset: 'classic',
      phase: 'focus',
      ...last,
    })
    expect(nextStartBody(idle({ next_phase: 'short_break', next_round: 2 }), last, classic)).toEqual({
      phase: 'short_break',
      ...last,
    })
    const custom = {
      preset: 'custom',
      focus_minutes: 40,
      short_break_minutes: 8,
      long_break_minutes: 20,
      rounds_before_long: 3,
    } as FocusSettings
    expect(nextStartBody(idle({ next_round: 2 }), last, custom)).toMatchObject({ preset: 'custom', focus_minutes: 40 })
  })
})

describe('popoutAlive (the presence rule)', () => {
  const base = {
    tabVisible: false,
    recentlyActive: false,
    popoutOpen: false,
    pastTarget: false,
    tappedSinceTarget: false,
  }

  it("keeps today's rule: a visible tab with a recent tap is present", () => {
    expect(popoutAlive({ ...base, tabVisible: true, recentlyActive: true })).toBe(true)
    expect(popoutAlive({ ...base, tabVisible: true })).toBe(false)
    expect(popoutAlive(base)).toBe(false)
  })

  it('counts an open pop-out until the target, with the tab hidden and nobody tapping', () => {
    expect(popoutAlive({ ...base, popoutOpen: true })).toBe(true)
  })

  it('stops counting it after the target, until a tap in the window', () => {
    expect(popoutAlive({ ...base, popoutOpen: true, pastTarget: true })).toBe(false)
    expect(popoutAlive({ ...base, popoutOpen: true, pastTarget: true, tappedSinceTarget: true })).toBe(true)
  })

  it('does nothing for a closed pop-out', () => {
    expect(popoutAlive({ ...base, pastTarget: true, tappedSinceTarget: true })).toBe(false)
  })
})

describe('presence across the target', () => {
  const target = at(1500)
  const fresh: PopoutPresence = { targetMs: target, tapMs: null }
  const window = PRESENCE_WINDOW_SECONDS * 1000

  it('is the end of a running phase, and nothing while paused or idle', () => {
    expect(phaseTarget(timer())).toBe(target)
    expect(phaseTarget(timer({ paused_total_seconds: 60 }))).toBe(target + 60_000)
    expect(phaseTarget(timer({ status: 'paused' }))).toBeNull()
    expect(phaseTarget(null)).toBeNull()
  })

  it('is before the target until the clock reaches it', () => {
    expect(presenceFlags(fresh, target - 1)).toEqual({ pastTarget: false, tappedSinceTarget: false })
    expect(presenceFlags(fresh, target)).toEqual({ pastTarget: true, tappedSinceTarget: false })
  })

  it('ignores a tap before the target', () => {
    expect(presenceAfterTap(fresh, target - 5000)).toBe(fresh)
  })

  it('counts the first tap within two minutes of the target and keeps it', () => {
    const tapped = presenceAfterTap(fresh, target + 90_000)
    expect(tapped.tapMs).toBe(target + 90_000)
    expect(presenceFlags(tapped, target + 3_600_000).tappedSinceTarget).toBe(true)
    expect(presenceAfterTap(tapped, target + 100_000)).toBe(tapped)
  })

  it('does not count a tap after two minutes: the round has already closed at its target', () => {
    expect(presenceAfterTap(fresh, target + window + 1).tapMs).toBeNull()
    expect(presenceAfterTap(fresh, target + window).tapMs).toBe(target + window)
  })

  it('has no tap to count without a target', () => {
    const none: PopoutPresence = { targetMs: null, tapMs: null }
    expect(presenceAfterTap(none, target)).toBe(none)
  })
})

describe('advanceRound (popout_session)', () => {
  const run = (steps: Array<[FocusTimer | null, boolean, number]>) => {
    let state = null as ReturnType<typeof advanceRound>['next']
    const reports = []
    for (const [t, open, seconds] of steps) {
      const out = advanceRound(state, t, open, at(seconds))
      state = out.next
      if (out.report) reports.push(out.report)
    }
    return reports
  }

  it('reports the seconds the window was open during a round that went past its target', () => {
    const t = timer()
    expect(
      run([
        [t, false, 0],
        [t, true, 300],
        [t, true, 1500],
        [timer({ client_id: 'next', phase: 'short_break' }), true, 1510],
      ]),
    ).toEqual([{ round_number: 2, completed: true, seconds_with_popout: 1210 }])
  })

  it('reports a round that ended early as not completed', () => {
    const t = timer()
    expect(
      run([
        [t, true, 0],
        [t, true, 120],
        [null, true, 130],
      ]),
    ).toEqual([{ round_number: 2, completed: false, seconds_with_popout: 130 }])
  })

  it('sends nothing for a round the window never saw, or for a break', () => {
    const t = timer()
    expect(
      run([
        [t, false, 0],
        [t, false, 600],
        [null, false, 700],
      ]),
    ).toEqual([])
    expect(
      run([
        [timer({ phase: 'short_break' }), true, 0],
        [null, true, 100],
      ]),
    ).toEqual([])
  })

  it('does not count time while the window is closed', () => {
    const t = timer()
    expect(
      run([
        [t, true, 0],
        [t, true, 100],
        [t, false, 100],
        [t, false, 900],
        [null, false, 910],
      ]),
    ).toEqual([{ round_number: 2, completed: false, seconds_with_popout: 100 }])
  })
})

describe('promptEligible (X-01 W4.3)', () => {
  const eligible = {
    supported: true,
    desktop: true,
    flagOn: true,
    popoutPromptSeen: false,
    popoutOnStart: false,
    phase: 'focus' as const,
    popoutOpen: false,
  }

  it('is true on a desktop browser with Document Picture-in-Picture, flag on, never seen, setting off, mid focus round', () => {
    expect(promptEligible(eligible)).toBe(true)
  })

  it.each([
    ['the browser has no Document Picture-in-Picture (Safari, Firefox below 151)', { supported: false }],
    ['it is not a desktop browser', { desktop: false }],
    ['the floating_timer flag is off', { flagOn: false }],
    ['the prompt was already shown once', { popoutPromptSeen: true }],
    ['pop out on start is already on', { popoutOnStart: true }],
    ['it is a short break', { phase: 'short_break' as const }],
    ['it is a long break', { phase: 'long_break' as const }],
    ['nothing runs', { phase: null }],
    ['a window is already open', { popoutOpen: true }],
  ])('is false when %s', (_why, patch) => {
    expect(promptEligible({ ...eligible, ...patch })).toBe(false)
  })
})

describe('shouldOpenOnStart (X-01 W4.3)', () => {
  const on = { available: true, popoutOnStart: true, popoutOpen: false }

  it('opens the window when the setting is on, the window is offered and none is open', () => {
    expect(shouldOpenOnStart(on)).toBe(true)
  })

  it.each([
    ['the window is not offered (no support, flag off or signed out)', { available: false }],
    ['the setting is off', { popoutOnStart: false }],
    ['a window is already open', { popoutOpen: true }],
  ])('does not when %s', (_why, patch) => {
    expect(shouldOpenOnStart({ ...on, ...patch })).toBe(false)
  })
})
