import { Badge, Briefcase, Button, Card, Input, Label, Switch } from '@artha/design-system'
import { useEffect, useState } from 'react'

import { useArticleship, useArticleshipMutation } from '../hooks/useProgression'
import type { StudyMode } from '../types'

const STRATEGY_MODES: Array<{
  id: StudyMode
  title: string
  badge: string
  description: string
  defaultWeekday: number
  defaultWeekend: number
}> = [
  {
    id: 'active_study',
    title: 'Active Study (Balanced)',
    badge: 'Recommended',
    description: 'Study 2 hours before/after office on weekdays, deep dive for 6 hours on weekends.',
    defaultWeekday: 120,
    defaultWeekend: 360,
  },
  {
    id: 'weekend_only',
    title: 'Weekend Warrior',
    badge: 'High Workload',
    description: 'Office demands full energy on weekdays. Dedicate Saturday and Sunday to deep study blocks.',
    defaultWeekday: 30,
    defaultWeekend: 420,
  },
  {
    id: 'work_focus_pause',
    title: 'Work-Focus Pause',
    badge: 'Audit / Tax Crunch',
    description: 'Peak busy season. Streaks frozen, zero overdue penalties, micro-recall suggestions for commute.',
    defaultWeekday: 30,
    defaultWeekend: 60,
  },
  {
    id: 'exam_leave_intensive',
    title: 'Exam Leave Intensive',
    badge: 'Full-time Ramp',
    description: 'Full-time study leave approved by your firm. Daily targets ramp to 8+ hours/day.',
    defaultWeekday: 480,
    defaultWeekend: 480,
  },
]

export function ArticleshipSettingsContainer() {
  const { data: articleship, isLoading } = useArticleship()
  const mutation = useArticleshipMutation()

  const [isActive, setIsActive] = useState<boolean>(articleship?.is_active ?? false)
  const [firmName, setFirmName] = useState<string>(articleship?.firm_name ?? '')
  const [registrationNumber, setRegistrationNumber] = useState<string>(articleship?.registration_number ?? '')
  const [trainingStartDate, setTrainingStartDate] = useState<string>(articleship?.training_start_date ?? '')
  const [expectedCompletionDate, setExpectedCompletionDate] = useState<string>(
    articleship?.expected_completion_date ?? '',
  )
  const [studyMode, setStudyMode] = useState<StudyMode>(articleship?.study_mode ?? 'active_study')
  const [weekdayMinutes, setWeekdayMinutes] = useState<number>(articleship?.weekday_minutes ?? 120)
  const [weekendMinutes, setWeekendMinutes] = useState<number>(articleship?.weekend_minutes ?? 360)
  const [examLeaveDate, setExamLeaveDate] = useState<string>(articleship?.exam_leave_start_date ?? '')
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false)

  // Sync initial data if fetched later
  useEffect(() => {
    if (articleship) {
      setIsActive(articleship.is_active)
      setFirmName(articleship.firm_name)
      setRegistrationNumber(articleship.registration_number)
      setTrainingStartDate(articleship.training_start_date ?? '')
      setExpectedCompletionDate(articleship.expected_completion_date ?? '')
      setStudyMode(articleship.study_mode)
      setWeekdayMinutes(articleship.weekday_minutes)
      setWeekendMinutes(articleship.weekend_minutes)
      setExamLeaveDate(articleship.exam_leave_start_date ?? '')
    }
  }, [articleship])

  const handleStudyModeSelect = (mode: StudyMode) => {
    setStudyMode(mode)
    const preset = STRATEGY_MODES.find((m) => m.id === mode)
    if (preset) {
      setWeekdayMinutes(preset.defaultWeekday)
      setWeekendMinutes(preset.defaultWeekend)
    }
  }

  const handleSave = async () => {
    setSavedSuccess(false)
    await mutation.mutateAsync({
      is_active: isActive,
      firm_name: firmName,
      registration_number: registrationNumber,
      training_start_date: trainingStartDate || null,
      expected_completion_date: expectedCompletionDate || null,
      study_mode: studyMode,
      weekday_minutes: weekdayMinutes,
      weekend_minutes: weekendMinutes,
      exam_leave_start_date: examLeaveDate || null,
    })
    setSavedSuccess(true)
    setTimeout(() => setSavedSuccess(false), 3000)
  }

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-6">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
          Articleship & Practical Training Planner
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Calibrate your weekday and weekend study split to balance firm workload with exam preparation.
        </p>
      </div>

      {/* Active Toggle Card */}
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
              <Briefcase className="size-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Active in Articleship / Practical Training</h3>
              <p className="text-xs text-muted-foreground">
                When active, your Today planner generates realistic morning and evening goals.
              </p>
            </div>
          </div>
          <Switch checked={isActive} onCheckedChange={setIsActive} aria-label="Toggle active articleship" />
        </div>
      </Card>

      {isActive && (
        <div className="space-y-6">
          {/* Firm & Registration Details */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="firm-name" className="text-xs font-semibold">
                Firm / Organization Name
              </Label>
              <Input
                id="firm-name"
                placeholder="e.g. BDO India, KPMG, Sole Proprietor"
                value={firmName}
                onChange={(e) => setFirmName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-num" className="text-xs font-semibold">
                Institute Training Registration Number (Optional)
              </Label>
              <Input
                id="reg-num"
                placeholder="e.g. SRO1234567/ART"
                value={registrationNumber}
                onChange={(e) => setRegistrationNumber(e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="start-date" className="text-xs font-semibold">
                Training Start Date
              </Label>
              <Input
                id="start-date"
                type="date"
                value={trainingStartDate}
                onChange={(e) => setTrainingStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="exam-leave-date" className="text-xs font-semibold">
                Planned Exam Leave Start Date
              </Label>
              <Input
                id="exam-leave-date"
                type="date"
                value={examLeaveDate}
                onChange={(e) => setExamLeaveDate(e.target.value)}
              />
            </div>
          </div>

          {/* Strategy Mode Picker */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold">Lifestyle Study Mode</Label>
            <div className="grid gap-3 sm:grid-cols-2">
              {STRATEGY_MODES.map((mode) => {
                const isSelected = studyMode === mode.id
                return (
                  <button
                    type="button"
                    key={mode.id}
                    onClick={() => handleStudyModeSelect(mode.id)}
                    className={`w-full cursor-pointer rounded-xl border p-4 text-left transition-all ${
                      isSelected ? 'border-primary bg-primary/5 ring-2 ring-primary/20' : 'hover:border-border/80'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-foreground">{mode.title}</span>
                      <Badge variant={isSelected ? 'default' : 'outline'} className="text-[10px]">
                        {mode.badge}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{mode.description}</p>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Weekday vs Weekend Split Sliders */}
          <div className="grid gap-4 sm:grid-cols-2">
            <Card className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-foreground">Weekday Study Target</h4>
                  <p className="text-xs text-muted-foreground">Monday to Friday (Morning & Night)</p>
                </div>
                <Badge variant="outline" className="font-mono text-xs font-bold">
                  {(weekdayMinutes / 60).toFixed(1)} hrs ({weekdayMinutes}m)
                </Badge>
              </div>
              <input
                type="range"
                min={15}
                max={360}
                step={15}
                value={weekdayMinutes}
                onChange={(e) => setWeekdayMinutes(Number(e.target.value))}
                className="mt-4 w-full accent-primary"
              />
            </Card>

            <Card className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-foreground">Weekend Study Target</h4>
                  <p className="text-xs text-muted-foreground">Saturday & Sunday deep study blocks</p>
                </div>
                <Badge variant="outline" className="font-mono text-xs font-bold">
                  {(weekendMinutes / 60).toFixed(1)} hrs ({weekendMinutes}m)
                </Badge>
              </div>
              <input
                type="range"
                min={60}
                max={720}
                step={30}
                value={weekendMinutes}
                onChange={(e) => setWeekendMinutes(Number(e.target.value))}
                className="mt-4 w-full accent-primary"
              />
            </Card>
          </div>
        </div>
      )}

      {/* Save Button */}
      <div className="flex items-center justify-between pt-4">
        {savedSuccess ? (
          <span className="text-sm font-semibold text-success">Preferences saved successfully!</span>
        ) : (
          <span />
        )}
        <Button onClick={() => void handleSave()} disabled={mutation.isPending}>
          {mutation.isPending ? 'Saving...' : 'Save Articleship Schedule'}
        </Button>
      </div>
    </div>
  )
}
