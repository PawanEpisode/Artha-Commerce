import { Alert, Page, PageHeader, SegmentedControl } from '@artha/design-system'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { FreshnessChip } from '../components/FreshnessChip'
import { MistakeBreakdown } from '../components/MistakeBreakdown'
import { OverviewCards } from '../components/OverviewCards'
import { PerformanceTable } from '../components/PerformanceTable'
import { ReadinessCard } from '../components/ReadinessCard'
import { ReportsView } from '../components/ReportsView'
import { SpeedMatrix } from '../components/SpeedMatrix'
import { WeakTopicsList } from '../components/WeakTopicsList'
import {
  useAnalyticsOverview,
  useMistakes,
  usePerformance,
  useReadiness,
  useSpeed,
  useWeakTopics,
} from '../hooks/useAnalytics'
import type { GroupByOption, RangeWindow } from '../lib/types'

type TabOption = 'overview' | 'explorer' | 'reports'

const TAB_OPTIONS: ReadonlyArray<{ value: TabOption; label: string }> = [
  { value: 'overview', label: 'Overview' },
  { value: 'explorer', label: 'Performance Explorer' },
  { value: 'reports', label: 'Reports & Sharing' },
]

export function AnalyticsDashboard() {
  const enabled = useFeatureFlag('performance_analytics', { strict: false })

  const [activeTab, setActiveTab] = React.useState<TabOption>('overview')
  const [range, setRange] = React.useState<RangeWindow>('30d')
  const [groupBy, setGroupBy] = React.useState<GroupByOption>('chapter')

  // Queries
  const { data: overview, isLoading: overviewLoading } = useAnalyticsOverview(range, enabled)
  const { data: readiness, isLoading: readinessLoading } = useReadiness(enabled)
  const { data: performance, isLoading: perfLoading } = usePerformance(groupBy, range, enabled)
  const { data: weakTopics, isLoading: weakLoading } = useWeakTopics(6, enabled)
  const { data: speed, isLoading: speedLoading } = useSpeed(range, enabled)
  const { data: mistakes, isLoading: mistakesLoading } = useMistakes(range, enabled)

  if (!enabled) {
    return (
      <Page width="form">
        <Alert variant="info">
          Performance Analytics is currently rolling out and not yet enabled for your account.
        </Alert>
      </Page>
    )
  }

  return (
    <Page width="fluid">
      <div className="space-y-6">
        <PageHeader
          title="Performance Analytics"
          description="Exam readiness index, Empirical Bayes mastery, and targeted improvement drills."
          actions={
            <div className="flex items-center gap-3">
              <FreshnessChip lastCalculatedAt={overview?.last_calculated_at} factsVersion={overview?.facts_version} />
              <SegmentedControl
                label="Analytics view"
                value={activeTab}
                onValueChange={setActiveTab}
                options={TAB_OPTIONS}
              />
            </div>
          }
        />

        {activeTab === 'overview' && (
          <div className="space-y-6">
            <OverviewCards data={overview} isLoading={overviewLoading} />

            <ReadinessCard data={readiness} isLoading={readinessLoading} />

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <WeakTopicsList data={weakTopics} isLoading={weakLoading} />
              <SpeedMatrix data={speed} isLoading={speedLoading} />
            </div>

            <MistakeBreakdown data={mistakes} isLoading={mistakesLoading} />
          </div>
        )}

        {activeTab === 'explorer' && (
          <PerformanceTable
            data={performance}
            isLoading={perfLoading}
            groupBy={groupBy}
            onGroupByChange={setGroupBy}
            range={range}
            onRangeChange={setRange}
          />
        )}

        {activeTab === 'reports' && <ReportsView />}
      </div>
    </Page>
  )
}
