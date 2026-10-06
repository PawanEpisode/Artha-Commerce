import { Skeleton } from '@artha/design-system'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { AlertsOutcomeCard, type OutcomeKind } from '../components/AlertsOutcomeCard'
import { AlertsPreCard } from '../components/AlertsPreCard'
import { InAppBrowserCard } from '../components/InAppBrowserCard'
import { InstallGuide } from '../components/InstallGuide'
import { TestPushControl } from '../components/TestPushControl'
import { UnblockSteps } from '../components/UnblockSteps'
import { useDevices, useNotificationSettings } from '../hooks/useNotificationQueries'
import { usePushCapability } from '../hooks/usePushCapability'
import { usePushEnable } from '../hooks/usePushEnable'
import { useRegistrationRefresh } from '../hooks/useRegistrationRefresh'
import { useTestPush } from '../hooks/useTestPush'
import {
  type AfterEnable,
  afterEnable,
  type AlertsBranch,
  alertsBranch,
  type AlertsResult,
  enableAnnouncement,
  resultFor,
  shouldRecordPrePrompt,
  stateFor,
} from '../lib/alertsStep'
import { notificationAnalytics } from '../lib/analytics'
import { isNotificationsDisabled, postPermissionState } from '../lib/api'
import { copyText } from '../lib/clipboard'
import { rememberedDeviceId } from '../lib/deviceMemory'
import { notificationKeys } from '../lib/keys'

interface Props {
  /** The student's choice is recorded; save the onboarding step and move on. Rejecting shows a retryable error. */
  onFinish: (result: AlertsResult) => Promise<void>
  /** Leave the step without recording a decision (alerts are not available in this build). */
  onSkip: () => Promise<void>
}

/**
 * The onboarding step `alerts` (PRD 5.1, FR-N2): reads what this browser can do, shows the one matching screen, runs
 * the browser prompt and registers the device on Allow, records every outcome as a consent decision (source
 * `onboarding`), and reports the result to the flow. Nothing here traps the student: every screen has a way on.
 */
export function AlertsStepContainer({ onFinish, onSkip }: Props) {
  const qc = useQueryClient()
  const capability = usePushCapability()
  const settings = useNotificationSettings()
  const devices = useDevices()
  const { enable, busy: enabling } = usePushEnable('onboarding')
  const test = useTestPush(devices.data, rememberedDeviceId(), () => void devices.refetch())

  const [after, setAfter] = useState<AfterEnable>(null)
  const [enableError, setEnableError] = useState<string | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const [finishing, setFinishing] = useState(false)
  const [finishFailed, setFinishFailed] = useState(false)
  const [checks, setChecks] = useState(0)
  const [checking, setChecking] = useState(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const previous = useRef<AlertsBranch>('checking')
  const viewed = useRef(false)
  const prePromptSent = useRef(false)

  const { environment, view } = capability
  const branch = alertsBranch(view, after)

  useRegistrationRefresh(view.kind === 'active')

  // PRD 10: one `alerts_step_viewed` per visit, once the browser has told us which screen applies.
  useEffect(() => {
    if (viewed.current || branch === 'checking' || !environment) return
    viewed.current = true
    notificationAnalytics.alertsStepViewed(branch, environment)
  }, [branch, environment])

  // Showing our own pre-prompt counts as an ask. Best effort: a failed record never blocks the student.
  useEffect(() => {
    if (prePromptSent.current || !shouldRecordPrePrompt(branch, settings.data?.permission_state)) return
    prePromptSent.current = true
    void postPermissionState('pre_prompt_shown', 'onboarding')
      .then(() => qc.invalidateQueries({ queryKey: notificationKeys.settings }))
      .catch(() => undefined)
  }, [branch, settings.data?.permission_state, qc])

  // When one screen replaces another the focused button disappears: move focus to the new card's heading.
  useEffect(() => {
    const was = previous.current
    previous.current = branch
    if (was !== 'checking' && was !== branch) heading.current?.focus()
  }, [branch])

  async function onEnable() {
    if (!environment) return
    setEnableError(null)
    setFinishFailed(false)
    const outcome = await enable(environment)
    await capability.refresh()
    await Promise.all([
      qc.invalidateQueries({ queryKey: notificationKeys.devices }),
      qc.invalidateQueries({ queryKey: notificationKeys.settings }),
    ])
    setAfter(afterEnable(outcome.status))
    setEnableError(outcome.status === 'error' ? enableAnnouncement('error') : null)
    setAnnouncement(enableAnnouncement(outcome.status))
  }

  async function finish() {
    const result = resultFor(branch)
    if (!result || !environment || finishing) return
    setFinishing(true)
    setFinishFailed(false)
    try {
      await postPermissionState(stateFor(result), 'onboarding')
      await onFinish(result)
      notificationAnalytics.alertsStepCompleted(result, environment)
    } catch {
      setFinishFailed(true)
    } finally {
      setFinishing(false)
    }
  }

  async function skip() {
    if (finishing) return
    setFinishing(true)
    setFinishFailed(false)
    try {
      await onSkip()
    } catch {
      setFinishFailed(true)
    } finally {
      setFinishing(false)
    }
  }

  async function checkAgain() {
    setChecking(true)
    try {
      await capability.refresh()
      setChecks((n) => n + 1)
    } finally {
      setChecking(false)
    }
  }

  async function copyLink() {
    const ok = await copyText(window.location.href)
    setAnnouncement(
      ok ? 'Link copied. Paste it into Chrome or Safari.' : 'Could not copy. Press and hold the address to copy it.',
    )
  }

  return (
    <div className="space-y-4">
      {/* One persistent polite region: outcomes are spoken here, so a screen reader hears them without moving focus. */}
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
      {isNotificationsDisabled(settings.error) ? (
        <AlertsOutcomeCard
          kind="not_configured"
          finishing={finishing}
          finishFailed={finishFailed}
          headingRef={heading}
          onContinue={() => void skip()}
        />
      ) : (
        <Branch
          branch={branch}
          app={view.kind === 'in_app_browser' ? view.app : 'an app'}
          browser={environment?.browser ?? 'other'}
          platform={environment?.platform ?? 'other'}
          heading={heading}
          enabling={enabling}
          finishing={finishing}
          finishFailed={finishFailed}
          enableError={enableError}
          checks={checks}
          checking={checking}
          onEnable={() => void onEnable()}
          onFinish={() => void finish()}
          onSkip={() => void skip()}
          onCheckAgain={() => void checkAgain()}
          onCopyLink={() => void copyLink()}
          onRetry={() => void onEnable()}
        >
          <TestPushControl
            status={test.status}
            canSend={test.canSend}
            hasDevice={test.target !== null}
            onSend={test.send}
          />
        </Branch>
      )}
    </div>
  )
}

interface BranchProps {
  branch: AlertsBranch
  app: string
  browser: React.ComponentProps<typeof UnblockSteps>['browser']
  platform: React.ComponentProps<typeof UnblockSteps>['platform']
  heading: React.Ref<HTMLHeadingElement>
  enabling: boolean
  finishing: boolean
  finishFailed: boolean
  enableError: string | null
  checks: number
  checking: boolean
  onEnable: () => void
  onFinish: () => void
  onSkip: () => void
  onCheckAgain: () => void
  onCopyLink: () => void
  onRetry: () => void
  /** The test control, shown inside the "on" card. */
  children: React.ReactNode
}

/** Which card shows for which branch. No logic beyond the mapping (the decisions are in `lib/alertsStep.ts`). */
function Branch(p: BranchProps) {
  const common = { finishing: p.finishing, finishFailed: p.finishFailed, headingRef: p.heading }
  switch (p.branch) {
    case 'checking':
      return (
        <div aria-busy="true">
          <span className="sr-only" role="status">
            Checking what this device allows…
          </span>
          <Skeleton className="h-64 w-full" />
        </div>
      )
    case 'in_app_browser':
      return <InAppBrowserCard {...common} app={p.app} onCopyLink={p.onCopyLink} onContinue={p.onFinish} />
    case 'install':
      return <InstallGuide {...common} onContinue={p.onFinish} />
    case 'blocked':
      return (
        <UnblockSteps
          {...common}
          browser={p.browser}
          platform={p.platform}
          checks={p.checks}
          checking={p.checking}
          onCheckAgain={p.onCheckAgain}
          onSkip={p.onFinish}
        />
      )
    case 'pre_prompt':
    case 'finish_setup':
      return (
        <AlertsPreCard
          {...common}
          mode={p.branch === 'pre_prompt' ? 'prompt' : 'finish_setup'}
          enabling={p.enabling}
          enableError={p.enableError}
          onEnable={p.onEnable}
          onNotNow={p.onFinish}
        />
      )
    case 'on':
      return (
        <AlertsOutcomeCard kind="on" {...common} onContinue={p.onFinish}>
          {p.children}
        </AlertsOutcomeCard>
      )
    case 'not_configured':
      return <AlertsOutcomeCard kind="not_configured" {...common} onContinue={p.onSkip} />
    case 'dismissed':
      return <AlertsOutcomeCard kind="dismissed" {...common} onContinue={p.onFinish} onRetry={p.onRetry} />
    case 'denied':
    case 'device_limit':
    case 'unsupported': {
      const kind: OutcomeKind = p.branch
      return <AlertsOutcomeCard kind={kind} {...common} onContinue={p.onFinish} />
    }
  }
}
