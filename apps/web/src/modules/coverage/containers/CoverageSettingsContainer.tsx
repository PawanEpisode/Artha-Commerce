import { Alert, Skeleton } from '@artha/design-system'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { fetchLevel } from '~/modules/syllabus'

import { DataControls } from '../components/DataControls'
import { ExclusionList } from '../components/ExclusionList'
import { SchemeSwitch } from '../components/SchemeSwitch'
import { SettingsForm } from '../components/SettingsForm'
import { StudyTargetsForm } from '../components/StudyTargetsForm'
import { TargetsImpactDialog } from '../components/TargetsImpactDialog'
import {
  useDeleteCoverageData,
  useResetSettings,
  useSaveSettings,
  useSaveTargets,
  useSetSubjectExclusion,
  useSwitchScheme,
} from '../hooks/useCoverageMutations'
import { useCoverageSettings } from '../hooks/useCoverageQueries'
import { exportCoverage } from '../lib/api'
import { notify } from '../lib/notify'
import type { CoverageSettings, Overview } from '../lib/types'
import { CoverageShell } from './CoverageShell'

function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

function StudyTargets({ settings }: { settings: CoverageSettings }) {
  const enabled = useFeatureFlag('study_targets')
  const targets = useSaveTargets(settings.targets)
  if (!enabled) return null
  return (
    <>
      <StudyTargetsForm
        key={JSON.stringify(settings.targets)}
        settings={settings}
        pending={targets.saving}
        onSave={(next) => void targets.request(next)}
      />
      <TargetsImpactDialog
        open={targets.pendingRaise !== null}
        impact={targets.pendingRaise?.impact ?? null}
        from={settings.targets}
        to={targets.pendingRaise?.next ?? settings.targets}
        pending={targets.saving}
        onConfirm={() => void targets.confirm()}
        onCancel={targets.cancel}
      />
    </>
  )
}

function Body({ overview }: { overview: Overview }) {
  const settings = useCoverageSettings()
  const save = useSaveSettings()
  const reset = useResetSettings()
  const exclusion = useSetSubjectExclusion()
  const switcher = useSwitchScheme()
  const wipe = useDeleteCoverageData()
  const [exporting, setExporting] = useState(false)

  const { enrollment } = overview
  const level = useQuery({
    queryKey: ['syllabus', 'level', enrollment.course.code.toLowerCase(), enrollment.level.code],
    queryFn: () => fetchLevel(enrollment.course.code.toLowerCase(), enrollment.level.code),
  })

  async function onExport() {
    setExporting(true)
    try {
      download('my-coverage-data.json', await exportCoverage())
      notify.dataExported()
    } catch (error) {
      notify.failed(error, 'We could not export your data. Please try again.', 'coverage-export')
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <header className="space-y-2">
        <h1 className="font-display text-3xl font-extrabold">Coverage settings</h1>
        <p className="text-muted-foreground">
          Tune how your progress is measured. Your history is never rewritten, only how it is shown.
        </p>
      </header>

      {settings.isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : settings.isError || !settings.data ? (
        <Alert variant="error">We could not load your settings.</Alert>
      ) : (
        <>
          <StudyTargets settings={settings.data} />
          <SettingsForm
            key={JSON.stringify(settings.data)}
            settings={settings.data}
            pending={save.isPending || reset.isPending}
            onSave={(next) => save.mutate({ settings: next, previous: settings.data })}
            onReset={() => reset.mutate()}
          />
        </>
      )}

      <ExclusionList
        subjects={overview.subjects}
        pending={exclusion.isPending}
        onChange={(s, excluded) =>
          exclusion.mutate({ subjectId: s.id, excluded, subjectKey: s.key, subjectName: s.name })
        }
      />

      <SchemeSwitch
        current={enrollment.scheme}
        options={level.data?.schemes ?? []}
        pending={switcher.isPending}
        summary={switcher.data?.switch_summary}
        onSwitch={(to) =>
          switcher.mutate({
            enrollmentId: enrollment.id,
            schemeId: to.id,
            fromCode: enrollment.scheme.code,
            toCode: to.code,
            toName: to.name,
          })
        }
      />

      <DataControls
        exporting={exporting}
        deleting={wipe.isPending}
        onExport={() => void onExport()}
        onDelete={() => wipe.mutate()}
      />
    </>
  )
}

export function CoverageSettingsContainer() {
  return <CoverageShell>{(overview) => <Body overview={overview} />}</CoverageShell>
}
