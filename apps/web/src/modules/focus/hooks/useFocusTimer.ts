import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef } from 'react'

import { QueuedOffline, writeOrQueue } from '~/modules/coverage'
import { track } from '~/modules/observability'
import { markActive, nowIso, nowMs, recentlyActive, setServerTime, trackerKeys, useTick } from '~/modules/tracker'

import {
  changeContext,
  claimRound,
  completePhase,
  errorCode,
  focusRequest,
  getTimer,
  isFeatureDisabled,
  newClientId,
  sendFocus,
  staleTimer,
  type StartBody,
} from '../lib/api'
import { focusKeys } from '../lib/keys'
import { HEARTBEAT_SECONDS } from '../lib/presets'
import { isFinished, localExtend, localPause, localResume, remainingSeconds } from '../lib/timer-math'
import type { EndReason, FocusState, FocusTimer } from '../lib/types'
import { useFocusAlerts } from './useFocusAlerts'

type Local = (t: FocusTimer) => FocusTimer | null
interface Action {
  online: ReturnType<(typeof focusRequest)[keyof typeof focusRequest]>
  queued: ReturnType<(typeof focusRequest)[keyof typeof focusRequest]>
  local?: Local
  /** Called with the answer, for analytics. */
  done?: (next: FocusState, before: FocusTimer | null) => void
}

/**
 * The one Pomodoro timer. The server owns the state; this hook reads it (a heartbeat every 20 s while the tab is
 * visible, and whenever the tab regains focus), derives the countdown from timestamps and sends each action with the
 * timer's `version`. Offline, an action is queued with the moment of the tap and shown optimistically.
 */
export function useFocusTimer() {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: focusKeys.timer,
    queryFn: async () => {
      const data = await getTimer(document.visibilityState === 'visible' && recentlyActive(5 * 60_000))
      setServerTime(data.server_time)
      return data
    },
    refetchInterval: (q) => (q.state.data?.timer ? HEARTBEAT_SECONDS * 1000 : false),
    refetchOnWindowFocus: true,
    retry: (count, error) => !isFeatureDisabled(error) && count < 1,
  })
  const state = query.data
  const timer = state?.timer ?? null
  useTick(timer?.status === 'running')

  useEffect(() => {
    if (!timer) return
    const events = ['pointerdown', 'keydown'] as const
    for (const e of events) window.addEventListener(e, markActive, { passive: true })
    return () => {
      for (const e of events) window.removeEventListener(e, markActive)
    }
  }, [timer])

  const quiet = useRef(false)
  const announcement = useFocusAlerts(timer, state?.settings, quiet)

  const put = useCallback(
    (next: Partial<FocusState>) =>
      qc.setQueryData<FocusState>(focusKeys.timer, (old) =>
        old
          ? { ...old, ...next }
          : ({ timer: null, idle: null, live: 'none', server_time: nowIso(), ...next } as FocusState),
      ),
    [qc],
  )
  const refresh = useCallback(() => qc.invalidateQueries({ queryKey: focusKeys.timer }), [qc])
  const refreshTime = useCallback(() => {
    void qc.invalidateQueries({ queryKey: focusKeys.sessions })
    void qc.invalidateQueries({ queryKey: trackerKeys.sessions })
    void qc.invalidateQueries({ queryKey: trackerKeys.goals })
    void qc.invalidateQueries({ queryKey: trackerKeys.reports })
    void qc.invalidateQueries({ queryKey: ['coverage'] })
  }, [qc])

  const act = useMutation({
    mutationFn: async (a: Action) => {
      const before = timer
      try {
        const next = await writeOrQueue({ clientId: newClientId(), ...a.queued }, () => sendFocus<FocusState>(a.online))
        setServerTime(next.server_time)
        put(next)
        a.done?.(next, before)
        if (next.outcome === 'saved' || next.session || before?.client_id !== next.timer?.client_id) refreshTime()
      } catch (error) {
        if (!(error instanceof QueuedOffline)) throw error
        if (a.local && before) put({ timer: a.local(before) })
        void qc.invalidateQueries({ queryKey: trackerKeys.offline })
      }
    },
    onError: (error) => {
      quiet.current = false
      const latest = staleTimer(error)
      if (latest !== undefined) put({ timer: latest })
      if (errorCode(error) === 'stale_version' || errorCode(error) === 'timer_already_active')
        track('focus_timer_conflict', { code: errorCode(error) })
      void refresh()
    },
  })

  const start = (body: Omit<StartBody, 'client_id' | 'at'>, meta: { has_subject: boolean; resumed_cycle: boolean }) => {
    quiet.current = true
    const client_id = newClientId()
    const req = focusRequest.start({ ...body, client_id, at: nowIso() })
    act.mutate(
      {
        online: req,
        queued: req,
        done: (next) => {
          if (!next.timer) return
          track(next.timer.phase === 'focus' ? 'focus_session_started' : 'focus_break_started', {
            preset: next.timer.preset,
            round_number: next.timer.round_number,
            has_subject: meta.has_subject,
            activity_type: next.timer.activity_type,
            resumed_cycle: meta.resumed_cycle,
          })
        },
      },
      {},
    )
  }

  const v = timer?.version
  const pause = () =>
    act.mutate({
      online: focusRequest.pause({ version: v, at: nowIso() }),
      queued: focusRequest.pause({ at: nowIso() }),
      local: (t) => localPause(t, nowIso()),
      done: (_n, b) => track('focus_session_paused', { round_number: b?.round_number }),
    })
  const resume = () =>
    act.mutate({
      online: focusRequest.resume({ version: v, at: nowIso() }),
      queued: focusRequest.resume({ at: nowIso() }),
      local: (t) => localResume(t, nowIso()),
      done: (_n, b) => track('focus_session_resumed', { round_number: b?.round_number }),
    })
  const extend = () =>
    act.mutate({
      online: focusRequest.extend({ version: v }),
      queued: focusRequest.extend({}),
      local: localExtend,
    })
  const skipBreak = () => {
    quiet.current = true
    act.mutate({
      online: focusRequest.skipBreak({ version: v }),
      queued: focusRequest.skipBreak({}),
      local: () => null,
      done: (_n, b) => track('focus_break_skipped', { phase: b?.phase }),
    })
  }
  const end = (save: boolean, reason?: EndReason) => {
    const client_id = timer?.client_id
    quiet.current = true
    act.mutate({
      online: focusRequest.end({ client_id, version: v, save, reason }),
      queued: focusRequest.end({ client_id, save, reason }),
      local: () => null,
      done: (next, b) =>
        track('focus_session_abandoned', {
          saved: save && next.outcome === 'saved',
          outcome: next.outcome,
          reason: reason ?? null,
          seconds: b ? b.planned_seconds - remainingSeconds(b, nowMs()) : 0,
        }),
    })
  }

  const complete = useMutation({
    mutationFn: async () => {
      const before = timer
      const next = await completePhase()
      setServerTime(next.server_time)
      put(next)
      refreshTime()
      if (before?.phase === 'focus')
        track('focus_session_completed', {
          preset: before.preset,
          round_number: before.round_number,
          planned_seconds: before.planned_seconds,
          pause_count: before.pause_count,
          extension_count: before.extension_count,
        })
    },
    onError: () => void refresh(),
  })

  const claim = useMutation({
    mutationFn: async (count: boolean) => {
      quiet.current = true
      const next = await claimRound(count, v)
      setServerTime(next.server_time)
      put(next)
      refreshTime()
      track('focus_away_claim', { counted: count })
    },
    onError: () => void refresh(),
  })

  const context = useMutation({
    mutationFn: async (patch: { subject_id?: string | null; chapter_id?: string | null; activity_type?: string }) => {
      if (!timer) return
      const next = await changeContext({ version: timer.version, ...patch })
      put(next)
    },
    onError: () => void refresh(),
  })

  // The countdown reached zero on this screen: ask the server to close the phase (once per phase).
  const completed = useRef<string | null>(null)
  const finished = timer ? isFinished(timer, nowMs()) : false
  useEffect(() => {
    if (!timer || !finished || completed.current === timer.client_id || complete.isPending) return
    completed.current = timer.client_id
    complete.mutate()
  }, [timer, finished, complete])

  return {
    query,
    state,
    timer,
    idle: state?.idle ?? null,
    settings: state?.settings,
    live: state?.live ?? 'none',
    announcement,
    remaining: timer ? remainingSeconds(timer, nowMs()) : 0,
    busy: act.isPending || complete.isPending || claim.isPending,
    error: act.error ?? complete.error ?? claim.error,
    clearError: () => act.reset(),
    featureDisabled: isFeatureDisabled(query.error),
    start,
    pause,
    resume,
    extend,
    skipBreak,
    end,
    claim,
    context,
  }
}

export type FocusTimerApi = ReturnType<typeof useFocusTimer>
