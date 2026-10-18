import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
  toast,
} from '@artha/design-system'
import { createFileRoute } from '@tanstack/react-router'
import * as React from 'react'

import { usePaperAnalysisSettings } from '~/modules/paperanalysis'
import { buildHead } from '~/modules/seo'

function AnalysisSettingsContainer() {
  const { data: settings, updateSettings, isLoading } = usePaperAnalysisSettings()

  const [windowSize, setWindowSize] = React.useState('6')
  const [includePractice, setIncludePractice] = React.useState(false)
  const [includeOlder, setIncludeOlder] = React.useState(true)
  const [isSaving, setIsSaving] = React.useState(false)

  React.useEffect(() => {
    if (settings) {
      setWindowSize(String(settings.window))
      setIncludePractice(settings.include_practice)
      setIncludeOlder(settings.include_older)
    }
  }, [settings])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await updateSettings({
        window: parseInt(windowSize),
        include_practice: includePractice,
        include_older: includeOlder,
      })
      toast.success('Paper analysis settings saved.')
    } catch {
      toast.error('Failed to update settings.')
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading settings...</div>
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Analysis & Planner Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Configure default past sitting windows and paper sources used in frequency calculations.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Historical Statistics Window</CardTitle>
          <CardDescription>
            The number of past exam sittings considered when computing chapter weights and frequencies.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-1.5">
            <span className="block text-xs font-medium text-foreground">Sittings Window</span>
            <Select value={windowSize} onValueChange={setWindowSize}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Select window" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="6">Last 6 sittings (Recommended)</SelectItem>
                <SelectItem value="10">Last 10 sittings</SelectItem>
                <SelectItem value="12">Last 12 sittings</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between border-t border-muted pt-2">
            <div>
              <span className="block text-xs font-medium text-foreground">Include practice papers (MTP/RTP)</span>
              <span className="block text-[11px] text-muted-foreground">
                Include Mock Test Papers and Revision Test Papers with downweighted scores.
              </span>
            </div>
            <Switch checked={includePractice} onCheckedChange={setIncludePractice} />
          </div>

          <div className="flex items-center justify-between border-t border-muted pt-2">
            <div>
              <span className="block text-xs font-medium text-foreground">Include carried older-scheme sittings</span>
              <span className="block text-[11px] text-muted-foreground">
                Carry forward comparable past papers across syllabus restructuring.
              </span>
            </div>
            <Switch checked={includeOlder} onCheckedChange={setIncludeOlder} />
          </div>

          <div className="flex justify-end pt-3">
            <Button onClick={handleSave} disabled={isSaving} size="sm">
              {isSaving ? 'Saving...' : 'Save Settings'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export const Route = createFileRoute('/app/settings/analysis')({
  head: () =>
    buildHead({
      title: 'Paper Analysis Settings',
      description: 'Historical sittings window, practice paper inclusion, and comparability options.',
      path: '/app/settings/analysis',
      noindex: true,
    }),
  component: AnalysisSettingsContainer,
})
