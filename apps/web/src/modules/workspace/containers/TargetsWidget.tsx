import { isCoverageOff, useCoverageSettings } from '~/modules/coverage'
import { useFeatureFlag } from '~/modules/observability'
import { useOnline } from '~/modules/personalization'

import { TargetsView } from '../components/TargetsView'
import { WidgetCard } from '../components/WidgetCard'
import { widgetState } from '../hooks/useWidgetState'
import { trackWidgetClicked } from '../hooks/useWorkspaceAnalytics'
import { targetRows, targetsHeading } from '../lib/targetsSummary'

/** Study targets at a glance (PRD 7.3, P2). Hidden when `study_targets` or coverage is off for the student. */
export function TargetsWidget() {
  const enabled = useFeatureFlag('study_targets')
  const settings = useCoverageSettings()
  const online = useOnline()
  if (!enabled || isCoverageOff(settings.error)) return null
  const data = settings.data
  return (
    <WidgetCard
      id="widget-targets"
      title="Study targets"
      state={widgetState(settings)}
      onRetry={() => void settings.refetch()}
      offline={!online}
      onInteract={() => trackWidgetClicked('targets')}
    >
      {data ? (
        <TargetsView
          heading={targetsHeading(data.targets_preset, data.target_presets)}
          rows={targetRows(data.targets)}
          confirmed={data.targets_confirmed}
        />
      ) : null}
    </WidgetCard>
  )
}
