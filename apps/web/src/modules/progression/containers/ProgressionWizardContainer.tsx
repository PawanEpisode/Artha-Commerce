import {
  Badge,
  Briefcase,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Celebration,
  Check,
  GraduationCap,
  Input,
  Label,
  Sparkles,
  Switch,
  Undo2,
} from '@artha/design-system'
import { useNavigate } from '@tanstack/react-router'
import { useMemo, useState } from 'react'

import { useProgressionStatus, useTransitionMutation } from '../hooks/useProgression'
import type { ArticleshipProfileData, PaperResultPayload, StudyMode, TransitionPayload, TransitionType } from '../types'

const OUTCOMES: Array<{
  type: TransitionType
  badge: string
  title: string
  description: string
  icon: typeof GraduationCap
}> = [
  {
    type: 'full_level_pass',
    badge: 'Graduation',
    title: 'Cleared Level Completely',
    description: 'Passed all groups of your current level. Graduate to the next tier (e.g. Intermediate → Final).',
    icon: GraduationCap,
  },
  {
    type: 'group_clearance',
    badge: 'Group Focus',
    title: 'Cleared Group(s)',
    description: 'Passed one group. Focus 100% of your daily study bandwidth and questions on the pending group.',
    icon: Check,
  },
  {
    type: 'exemption_update',
    badge: '60+ Exemption',
    title: 'Paper Exemptions',
    description: 'Scored 60% or more in specific papers. Exclude them from study goals and carry forward credit.',
    icon: Sparkles,
  },
  {
    type: 'repeat_attempt',
    badge: 'Fresh Plan',
    title: 'Re-attempt / Syllabus Refresh',
    description:
      'Recalibrate your study schedule, review weak chapter analytics, and start fresh for the next attempt.',
    icon: Undo2,
  },
]

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

export function ProgressionWizardContainer() {
  const navigate = useNavigate()
  const { data: statusData, isLoading } = useProgressionStatus()
  const transitionMutation = useTransitionMutation()

  // Wizard Step (1: Outcome, 2: Papers/Groups, 3: Articleship, 4: Review)
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1)

  // Form State
  const [selectedOutcome, setSelectedOutcome] = useState<TransitionType>('full_level_pass')
  const [targetLevelCode, setTargetLevelCode] = useState<string>('')
  const [clearedGroups, setClearedGroups] = useState<Record<string, boolean>>({})
  const [paperMarks, setPaperMarks] = useState<Record<string, { marks: string; isPermanent: boolean }>>({})

  // Articleship State
  const [isArticleshipActive, setIsArticleshipActive] = useState<boolean>(false)
  const [firmName, setFirmName] = useState<string>('')
  const [studyMode, setStudyMode] = useState<StudyMode>('active_study')
  const [weekdayMinutes, setWeekdayMinutes] = useState<number>(120)
  const [weekendMinutes, setWeekendMinutes] = useState<number>(360)
  const [examLeaveDate, setExamLeaveDate] = useState<string>('')

  // Completion State
  const [celebrationData, setCelebrationData] = useState<{ title: string; message: string } | null>(null)

  const activeEnr = statusData?.active_enrollment
  const groups = useMemo(() => statusData?.current_groups || [], [statusData?.current_groups])

  // Collect all papers across groups
  const allPapers = useMemo(() => groups.flatMap((g) => g.papers), [groups])

  // Compute default target level
  const availableNextLevel = useMemo(() => {
    const nextTransition = statusData?.available_transitions.find((t) => t.type === 'full_level_pass')
    return nextTransition?.target_level_code || 'final'
  }, [statusData])

  const handleOutcomeSelect = (type: TransitionType) => {
    setSelectedOutcome(type)
    if (type === 'full_level_pass') {
      setTargetLevelCode(availableNextLevel)
    }
    setStep(2)
  }

  const handleGroupToggle = (groupKey: string) => {
    setClearedGroups((prev) => ({
      ...prev,
      [groupKey]: !prev[groupKey],
    }))
  }

  const handleMarksChange = (subjectKey: string, marksVal: string) => {
    setPaperMarks((prev) => ({
      ...prev,
      [subjectKey]: {
        marks: marksVal,
        isPermanent: prev[subjectKey]?.isPermanent ?? false,
      },
    }))
  }

  const handlePermanentToggle = (subjectKey: string) => {
    setPaperMarks((prev) => ({
      ...prev,
      [subjectKey]: {
        marks: prev[subjectKey]?.marks ?? '',
        isPermanent: !(prev[subjectKey]?.isPermanent ?? false),
      },
    }))
  }

  const handleStudyModeSelect = (mode: StudyMode) => {
    setStudyMode(mode)
    const preset = STRATEGY_MODES.find((m) => m.id === mode)
    if (preset) {
      setWeekdayMinutes(preset.defaultWeekday)
      setWeekendMinutes(preset.defaultWeekend)
    }
  }

  const handleSubmit = async () => {
    const paperResultsPayload: PaperResultPayload[] = Object.entries(paperMarks)
      .filter(([_, data]) => data.marks.trim() !== '')
      .map(([key, data]) => {
        const num = parseInt(data.marks, 10)
        return {
          subject_key: key,
          status: num >= 60 ? 'exempted' : num >= 40 ? 'passed' : 'failed',
          marks: isNaN(num) ? null : num,
          is_permanent: data.isPermanent,
        }
      })

    const clearedGroupKeys = Object.entries(clearedGroups)
      .filter(([_, cleared]) => cleared)
      .map(([key]) => key)

    const articleshipPayload: Partial<ArticleshipProfileData> = {
      is_active: isArticleshipActive,
      firm_name: firmName,
      study_mode: studyMode,
      weekday_minutes: weekdayMinutes,
      weekend_minutes: weekendMinutes,
      exam_leave_start_date: examLeaveDate ? examLeaveDate : null,
    }

    const payload: TransitionPayload = {
      transition_type: selectedOutcome,
      trigger: 'user_initiated',
      target_level_code: selectedOutcome === 'full_level_pass' ? targetLevelCode || availableNextLevel : null,
      cleared_group_keys: selectedOutcome === 'group_clearance' ? clearedGroupKeys : undefined,
      paper_results: paperResultsPayload.length > 0 ? paperResultsPayload : undefined,
      articleship: isArticleshipActive || articleshipPayload.firm_name ? articleshipPayload : null,
    }

    try {
      const res = await transitionMutation.mutateAsync(payload)
      setCelebrationData({
        title: selectedOutcome === 'full_level_pass' ? 'Graduation Complete!' : 'Workspace Calibrated!',
        message: res.message,
      })
    } catch {
      // Handled by react-query mutation error
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (celebrationData) {
    return (
      <Celebration
        title={celebrationData.title}
        message={celebrationData.message}
        ctaLabel="Open My New Workspace"
        onContinue={() => void navigate({ to: '/app' })}
      />
    )
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Step Indicator Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground md:text-3xl">
              Progression & Level Transition
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Calibrate your syllabus, exemptions, and study routine for your next term attempt.
            </p>
          </div>
          {activeEnr ? (
            <Badge variant="outline" className="h-7 px-3 text-xs font-semibold uppercase">
              {activeEnr.course_code} • {activeEnr.level_name}
            </Badge>
          ) : null}
        </div>

        {/* Stepper Progress Bar */}
        <div className="mt-6 flex items-center gap-2">
          {[
            { num: 1, label: 'Outcome' },
            { num: 2, label: 'Configuration' },
            { num: 3, label: 'Routine' },
            { num: 4, label: 'Review' },
          ].map((s) => (
            <div key={s.num} className="flex flex-1 items-center gap-2">
              <div
                className={`flex size-7 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                  step === s.num
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : step > s.num
                      ? 'bg-primary/20 text-primary'
                      : 'bg-muted text-muted-foreground'
                }`}
              >
                {step > s.num ? <Check className="size-3.5" /> : s.num}
              </div>
              <span
                className={`hidden text-xs font-medium sm:inline ${
                  step === s.num ? 'text-foreground' : 'text-muted-foreground'
                }`}
              >
                {s.label}
              </span>
              {s.num < 4 && <div className="h-px flex-1 bg-border" />}
            </div>
          ))}
        </div>
      </div>

      {/* STEP 1: Outcome Selection */}
      {step === 1 && (
        <div className="space-y-6">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-foreground">Select your term outcome</h2>
            <p className="text-sm text-muted-foreground">
              Choose the option that describes your recent exam results or transition goal.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {OUTCOMES.map((item) => {
              const Icon = item.icon
              const isSelected = selectedOutcome === item.type
              return (
                <Card
                  key={item.type}
                  className={`cursor-pointer transition-all hover:border-primary/50 hover:shadow-md ${
                    isSelected ? 'border-primary bg-primary/5 ring-2 ring-primary/20' : ''
                  }`}
                  onClick={() => handleOutcomeSelect(item.type)}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
                        <Icon className="size-5" />
                      </div>
                      <Badge variant={isSelected ? 'default' : 'outline'} className="text-[11px]">
                        {item.badge}
                      </Badge>
                    </div>
                    <CardTitle className="mt-3 text-base">{item.title}</CardTitle>
                    <CardDescription className="text-xs leading-relaxed">{item.description}</CardDescription>
                  </CardHeader>
                </Card>
              )
            })}
          </div>
        </div>
      )}

      {/* STEP 2: Paper & Group Configuration */}
      {step === 2 && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <h2 className="text-lg font-semibold text-foreground">
                {selectedOutcome === 'full_level_pass' && 'Target Level & Attempt'}
                {selectedOutcome === 'group_clearance' && 'Select Cleared Group'}
                {selectedOutcome === 'exemption_update' && 'Record Paper Marks & Exemptions'}
                {selectedOutcome === 'repeat_attempt' && 'Re-attempt Diagnostic Review'}
              </h2>
              <p className="text-sm text-muted-foreground">
                Configure papers and enter marks to automatically calculate official exemptions.
              </p>
            </div>
          </div>

          {/* Full Level Pass: Target level picker */}
          {selectedOutcome === 'full_level_pass' && (
            <Card className="border-primary/30 bg-primary/5 p-5">
              <div className="flex items-center gap-3">
                <div className="grid size-10 place-items-center rounded-lg bg-primary text-primary-foreground">
                  <GraduationCap className="size-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">Next Tier: {availableNextLevel.toUpperCase()}</h3>
                  <p className="text-xs text-muted-foreground">
                    Your current {activeEnr?.level_name} notes and documents will be preserved in your Past Level Vault.
                  </p>
                </div>
              </div>
            </Card>
          )}

          {/* Group Clearance: Group checkboxes */}
          {selectedOutcome === 'group_clearance' && (
            <div className="space-y-3">
              <Label className="text-sm font-semibold">Which group(s) did you clear?</Label>
              <div className="grid gap-3 sm:grid-cols-2">
                {groups.map((g) => {
                  const isChecked = Boolean(clearedGroups[g.key])
                  return (
                    <button
                      type="button"
                      key={g.key}
                      onClick={() => handleGroupToggle(g.key)}
                      className={`flex w-full cursor-pointer items-center justify-between rounded-xl border p-4 text-left transition-all ${
                        isChecked ? 'border-primary bg-primary/5 ring-2 ring-primary/20' : 'hover:border-border/80'
                      }`}
                    >
                      <div>
                        <p className="font-semibold text-foreground">{g.name}</p>
                        <p className="text-xs text-muted-foreground">{g.papers.length} Papers included</p>
                      </div>
                      <div
                        className={`grid size-6 place-items-center rounded-md border ${
                          isChecked ? 'border-primary bg-primary text-primary-foreground' : 'border-muted-foreground/30'
                        }`}
                      >
                        {isChecked && <Check className="size-4" />}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Paper-Wise Marks & Exemption Checklist */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-semibold">Paper Results & Marks</Label>
              <span className="text-xs text-muted-foreground">
                Scoring ≥ 60 marks automatically awards an Exemption
              </span>
            </div>

            <div className="space-y-3">
              {allPapers.map((paper) => {
                const markInfo = paperMarks[paper.key] || { marks: '', isPermanent: false }
                const markNum = parseInt(markInfo.marks, 10)
                const isExempted = !isNaN(markNum) && markNum >= 60

                return (
                  <div
                    key={paper.key}
                    className={`flex flex-col gap-3 rounded-xl border p-4 transition-all sm:flex-row sm:items-center sm:justify-between ${
                      isExempted ? 'border-amber-500/50 bg-amber-500/5' : 'bg-card'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        {paper.paper_number && (
                          <span className="text-xs font-semibold text-muted-foreground">
                            Paper {paper.paper_number}:
                          </span>
                        )}
                        <h4 className="truncate text-sm font-semibold text-foreground">{paper.name}</h4>
                      </div>
                      {isExempted ? (
                        <div className="mt-1 flex items-center gap-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
                          <Sparkles className="size-3.5" />
                          <span>Official 60+ Exemption Granted! Valid for 3 terms.</span>
                        </div>
                      ) : (
                        <p className="mt-0.5 text-xs text-muted-foreground">Total Marks: {paper.total_marks}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        <Label htmlFor={`marks-${paper.key}`} className="text-xs text-muted-foreground">
                          Marks:
                        </Label>
                        <Input
                          id={`marks-${paper.key}`}
                          type="number"
                          min={0}
                          max={100}
                          placeholder="e.g. 64"
                          value={markInfo.marks}
                          onChange={(e) => handleMarksChange(paper.key, e.target.value)}
                          className="h-8 w-20 text-center font-semibold"
                        />
                      </div>

                      {isExempted && (
                        <Button
                          type="button"
                          variant={markInfo.isPermanent ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => handlePermanentToggle(paper.key)}
                          className="h-8 text-xs"
                        >
                          {markInfo.isPermanent ? 'Permanent' : 'Make Permanent'}
                        </Button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="flex justify-between pt-4">
            <Button variant="outline" onClick={() => setStep(1)}>
              Back
            </Button>
            <Button onClick={() => setStep(3)}>Continue to Routine Setup</Button>
          </div>
        </div>
      )}

      {/* STEP 3: Articleship & Routine Setup */}
      {step === 3 && (
        <div className="space-y-6">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-foreground">Articleship & Study Routine</h2>
            <p className="text-sm text-muted-foreground">
              Configure your practical training constraints so your daily Today planner generates realistic goals.
            </p>
          </div>

          {/* Articleship Active Toggle */}
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
                  <Briefcase className="size-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">
                    Are you currently in Practical Training / Articleship?
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Adapts study hours from 8–10 hrs/day to realistic office-friendly schedules (2–3 hrs/day).
                  </p>
                </div>
              </div>
              <Switch
                checked={isArticleshipActive}
                onCheckedChange={setIsArticleshipActive}
                aria-label="Toggle articleship status"
              />
            </div>
          </Card>

          {isArticleshipActive ? (
            <div className="space-y-6">
              {/* Firm Details */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="firm-name" className="text-xs font-semibold">
                    Firm / Employer Name
                  </Label>
                  <Input
                    id="firm-name"
                    placeholder="e.g. BDO India, Deloitte, Sole Proprietorship"
                    value={firmName}
                    onChange={(e) => setFirmName(e.target.value)}
                    className="h-9"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="exam-leave" className="text-xs font-semibold">
                    Planned Exam Leave Start Date (Optional)
                  </Label>
                  <Input
                    id="exam-leave"
                    type="date"
                    value={examLeaveDate}
                    onChange={(e) => setExamLeaveDate(e.target.value)}
                    className="h-9"
                  />
                </div>
              </div>

              {/* Study Mode Strategy */}
              <div className="space-y-3">
                <Label className="text-sm font-semibold">Study Strategy Mode</Label>
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

              {/* Weekday & Weekend Hours Adjusters */}
              <div className="grid gap-4 sm:grid-cols-2">
                <Card className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-foreground">Weekday Study Target</h4>
                      <p className="text-xs text-muted-foreground">Monday to Friday (before/after office)</p>
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
                      <p className="text-xs text-muted-foreground">Saturday & Sunday deep blocks</p>
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
          ) : (
            /* Full-Time Student Hours */
            <Card className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-foreground">Full-Time Daily Study Goal</h4>
                  <p className="text-xs text-muted-foreground">Planned daily minutes across weekdays and weekends</p>
                </div>
                <Badge variant="outline" className="font-mono text-sm font-bold">
                  {(weekdayMinutes / 60).toFixed(1)} hrs/day
                </Badge>
              </div>
              <input
                type="range"
                min={120}
                max={720}
                step={30}
                value={weekdayMinutes}
                onChange={(e) => {
                  const val = Number(e.target.value)
                  setWeekdayMinutes(val)
                  setWeekendMinutes(val)
                }}
                className="mt-5 w-full accent-primary"
              />
            </Card>
          )}

          <div className="flex justify-between pt-4">
            <Button variant="outline" onClick={() => setStep(2)}>
              Back
            </Button>
            <Button onClick={() => setStep(4)}>Review Transformation</Button>
          </div>
        </div>
      )}

      {/* STEP 4: Review & Confirm */}
      {step === 4 && (
        <div className="space-y-6">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-foreground">Review & Instant Workspace Calibration</h2>
            <p className="text-sm text-muted-foreground">
              Confirm your progression transformation. All changes take effect atomically.
            </p>
          </div>

          {/* Transformation Summary Card */}
          <Card className="overflow-hidden border-primary/20">
            <div className="border-b bg-muted/30 px-6 py-4">
              <h3 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
                Workspace Transformation Overview
              </h3>
            </div>
            <CardContent className="divide-y p-0">
              <div className="grid grid-cols-2 p-4 text-sm sm:grid-cols-4">
                <div>
                  <p className="text-xs text-muted-foreground">Outcome Type</p>
                  <p className="font-semibold text-foreground capitalize">{selectedOutcome.replace(/_/g, ' ')}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Target Tier</p>
                  <p className="font-semibold text-foreground">
                    {selectedOutcome === 'full_level_pass' ? availableNextLevel.toUpperCase() : activeEnr?.level_name}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Daily Schedule</p>
                  <p className="font-semibold text-foreground">
                    {isArticleshipActive
                      ? `${(weekdayMinutes / 60).toFixed(1)}h Wkday / ${(weekendMinutes / 60).toFixed(1)}h Wkend`
                      : `${(weekdayMinutes / 60).toFixed(1)} hrs/day`}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Articleship Mode</p>
                  <p className="font-semibold text-foreground capitalize">
                    {isArticleshipActive ? studyMode.replace(/_/g, ' ') : 'Full-time'}
                  </p>
                </div>
              </div>

              {/* Past Level Vault note */}
              <div className="flex items-start gap-3 bg-primary/5 p-4 text-xs text-muted-foreground">
                <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
                <p>
                  <strong className="text-foreground">Past Level Vault Protection:</strong> Your completed level notes,
                  drawings, and analytics are never deleted. They will remain accessible anytime in your{' '}
                  <span className="font-medium text-foreground">Past Level Vault</span>.
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-between pt-4">
            <Button variant="outline" onClick={() => setStep(3)}>
              Back
            </Button>
            <Button
              size="lg"
              onClick={() => void handleSubmit()}
              disabled={transitionMutation.isPending}
              className="gap-2 shadow-md"
            >
              {transitionMutation.isPending ? (
                <>Applying Calibration...</>
              ) : (
                <>
                  Confirm & Launch Workspace
                  <Sparkles className="size-4" />
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
