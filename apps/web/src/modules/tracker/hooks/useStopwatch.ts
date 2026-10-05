import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'

import { QueuedOffline, writeOrQueue } from '~/modules/coverage'
import { track } from '~/modules/observability'

import {
  answerIdle,
  changeContext,
  getStopwatch,
  isFeatureDisabled,
  newClientId,
  sendStopwatch,
  stopwatchRequest,
} from '../lib/api'
import { markActive, nowIso, nowMs, recentlyActive, setServerTime } from '../lib/clock'
import { elapsedSeconds } from '../lib/duration'
import { trackerKeys } from '../lib/keys'
import { localPause, localResume, localStart } from '../lib/stopwatchLocal'
import type { ActivityType, StopResult, StopwatchState } from '../lib/types'

export interface TimerContext {
  subject_id: string | null
  chapter_id: string | null
  activity_type: ActivityType
}

/** Ticks once a second so the clock re-renders. The value shown is always derived from timestamps, never counted. */
export function useTick(active: boolean, everyMs = 1000) {
  const [, set] = useState(0)
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => set((n) => n + 1), everyMs)
    return () => window.clearInterval(id)
  }, [active, everyMs])
}

/** Lets the server see that the student is at the screen: any pointer or key event counts. */
function useActivityMarker(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return
    const events = ['pointerdown', 'keydown', 'pointermove', 'touchstart'] as const
    for (const e of events) window.addEventListener(e, markActive, { passive: true })
    return () => {
      for (const e of events) window.removeEventListener(e, markActive)
    }
  }, [enabled])
}

/**
 * The one active stopwatch. Reads the server's state (heartbeat every 30 s while it runs), applies each action
 * optimistically and queues it with the corrected moment when the network is down. The elapsed time comes from
 * timestamps, so a sleeping tab or a reload shows the right number.
 */
export function useStopwatch() {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: trackerKeys.stopwatch,
    queryFn: async () => {
      const data = await getStopwatch({ alive: true, active: recentlyActive() })
      setServerTime(data.server_time)
      return data
    },
    refetchInterval: (q) => (q.state.data?.stopwatch ? 30_000 : false),
    refetchOnWindowFocus: true,
    retry: (count, error) => !isFeatureDisabled(error) && count < 1,
  })
  const state = query.data
  const sw = state?.stopwatch ?? null
  useTick(sw?.status === 'running')
  useActivityMarker(sw !== null)

  const put = useCallback(
    (next: Partial<StopwatchState> & { stopwatch: StopwatchState['stopwatch'] }) =>
      qc.setQueryData<StopwatchState>(trackerKeys.stopwatch, (old) => ({
        live: null,
        idle_minutes: 10,
        server_time: nowIso(),
        ...old,
        ...next,
      })),
    [qc],
  )
  const refresh = useCallback(() => qc.invalidateQueries({ queryKey: trackerKeys.stopwatch }), [qc])
  const afterWrite = useCallback(() => {
    void qc.invalidateQueries({ queryKey: trackerKeys.offline })
  }, [qc])

  const start = useMutation({
    mutationFn: async (context: TimerContext) => {
      const clientId = newClientId()
      const at = nowIso()
      const req = stopwatchRequest.start({ client_id: clientId, ...context, at })
      try {
        const next = await writeOrQueue({ clientId, ...req }, () => sendStopwatch<StopwatchState>(req))
        setServerTime(next.server_time)
        put(next)
        track('stopwatch_started', { activity_type: context.activity_type, has_subject: !!context.subject_id })
      } catch (error) {
        if (!(error instanceof QueuedOffline)) throw error
        put({ stopwatch: localStart(at, clientId, context) })
        track('stopwatch_started', {
          activity_type: context.activity_type,
          has_subject: !!context.subject_id,
          queued: true,
        })
        afterWrite()
      }
    },
    onError: (error) => {
      if ((error as { status?: number }).status === 409) track('timer_conflict', { kind: 'stopwatch_start' })
      void refresh()
    },
  })

  const toggle = useMutation({
    mutationFn: async (kind: 'pause' | 'resume') => {
      if (!sw) return
      const at = nowIso()
      const online = stopwatchRequest[kind]({ at, version: sw.version })
      const queued = stopwatchRequest[kind]({ at })
      try {
        const next = await writeOrQueue({ clientId: newClientId(), ...queued }, () =>
          sendStopwatch<StopwatchState>(online),
        )
        put(next)
      } catch (error) {
        if (!(error instanceof QueuedOffline)) throw error
        put({ stopwatch: kind === 'pause' ? localPause(sw, at) : localResume(sw, at) })
        afterWrite()
      }
    },
    onError: () => void refresh(),
  })

  const stop = useMutation({
    mutationFn: async (save: boolean) => {
      if (!sw) return null
      const body = { client_id: sw.client_id, end_at: nowIso(), save }
      const queued = stopwatchRequest.stop(body)
      const online = stopwatchRequest.stop({ ...body, version: sw.version })
      const counted = elapsedSeconds(sw, nowMs())
      try {
        const result = await writeOrQueue({ clientId: newClientId(), ...queued }, () =>
          sendStopwatch<StopResult>(online),
        )
        put({ stopwatch: null })
        track('stopwatch_stopped', { seconds: counted, saved: save, outcome: result.outcome })
        return result
      } catch (error) {
        if (!(error instanceof QueuedOffline)) throw error
        put({ stopwatch: null })
        track('stopwatch_stopped', { seconds: counted, saved: save, queued: true })
        afterWrite()
        return null
      }
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: trackerKeys.sessions })
      void qc.invalidateQueries({ queryKey: trackerKeys.goals })
      void qc.invalidateQueries({ queryKey: trackerKeys.reports })
      void qc.invalidateQueries({ queryKey: ['coverage'] })
      void refresh()
    },
  })

  const context = useMutation({
    mutationFn: async (patch: Partial<TimerContext>) => {
      if (!sw) return
      const next = await changeContext({ version: sw.version, ...patch })
      put(next)
    },
    onError: () => void refresh(),
  })

  const idle = useMutation({
    mutationFn: async (answer: 'prompted' | 'still_studying') => {
      const next = await answerIdle(answer)
      put(next)
      if (answer === 'prompted') track('stopwatch_idle_prompted')
    },
    onError: () => void refresh(),
  })

  const seconds = sw ? elapsedSeconds(sw, nowMs()) : 0
  return {
    query,
    state,
    stopwatch: sw,
    seconds,
    busy: start.isPending || toggle.isPending || stop.isPending,
    featureDisabled: isFeatureDisabled(query.error),
    start,
    toggle,
    stop,
    context,
    idle,
  }
}
