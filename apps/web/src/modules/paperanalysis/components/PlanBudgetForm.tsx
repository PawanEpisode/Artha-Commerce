import { Button, Checkbox, Slider, Switch } from '@artha/design-system'

import type { SubjectStatus } from '../types'

export interface PlanBudgetFormProps {
  subjects: SubjectStatus[]
  days: number
  hoursPerDay: number
  selectedSubjects: string[]
  balanceSubjects: boolean
  isLoading?: boolean
  onChangeDays: (days: number) => void
  onChangeHours: (hours: number) => void
  onToggleSubject: (subjectKey: string) => void
  onChangeBalance: (balance: boolean) => void
  onSubmit: () => void
}

export function PlanBudgetForm({
  subjects,
  days,
  hoursPerDay,
  selectedSubjects,
  balanceSubjects,
  isLoading = false,
  onChangeDays,
  onChangeHours,
  onToggleSubject,
  onChangeBalance,
  onSubmit,
}: PlanBudgetFormProps) {
  const totalBudget = Math.round(days * hoursPerDay * 0.9)

  return (
    <div className="space-y-5 rounded-2xl border border-border bg-card p-5 shadow-xs">
      <div>
        <h2 className="text-base font-semibold text-foreground">Plan Parameters</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Greedy selection prioritises chapters with the highest historical marks yield per hour of revision effort.
        </p>
      </div>

      {/* Days Slider */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <label htmlFor="plan-days-slider" className="font-medium text-foreground">
            Days available
          </label>
          <span className="font-mono font-semibold text-primary">{days} days</span>
        </div>
        <Slider
          id="plan-days-slider"
          label="Days available"
          min={1}
          max={60}
          step={1}
          value={days}
          onValueChange={onChangeDays}
        />
        <div className="flex justify-between text-[11px] text-muted-foreground">
          <span>1 day</span>
          <span>30 days</span>
          <span>60 days</span>
        </div>
      </div>

      {/* Hours per Day Slider */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <label htmlFor="plan-hours-slider" className="font-medium text-foreground">
            Daily study budget
          </label>
          <span className="font-mono font-semibold text-primary">{hoursPerDay} hours/day</span>
        </div>
        <Slider
          id="plan-hours-slider"
          label="Daily study budget"
          min={1}
          max={12}
          step={0.5}
          value={hoursPerDay}
          onValueChange={onChangeHours}
        />
        <div className="flex justify-between text-[11px] text-muted-foreground">
          <span>1h</span>
          <span>6h</span>
          <span>12h</span>
        </div>
      </div>

      {/* Effective Study Budget summary */}
      <div className="flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs">
        <span className="text-muted-foreground">Total usable revision time (with 10% buffer):</span>
        <strong className="font-mono text-sm font-semibold text-primary">{totalBudget} hours</strong>
      </div>

      {/* Subject Selection */}
      <div className="space-y-2">
        <span className="text-sm font-medium text-foreground">Include subjects</span>
        <div className="grid grid-cols-1 gap-2 pt-1 sm:grid-cols-2">
          {subjects.map((sub) => {
            const isChecked = selectedSubjects.includes(sub.subject_key)
            return (
              <label
                key={sub.subject_key}
                className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-muted p-2 text-xs hover:bg-muted/40"
              >
                <Checkbox checked={isChecked} onCheckedChange={() => onToggleSubject(sub.subject_key)} />
                <span className="truncate font-medium text-foreground">{sub.subject_name || sub.subject_key}</span>
              </label>
            )
          })}
        </div>
      </div>

      {/* Balance subjects toggle */}
      <div className="flex items-center justify-between border-t border-muted pt-2">
        <div>
          <span className="block text-xs font-medium text-foreground">Balance revision across subjects</span>
          <span className="block text-[11px] text-muted-foreground">
            Guarantees proportional time allocation across all selected subjects
          </span>
        </div>
        <Switch checked={balanceSubjects} onCheckedChange={onChangeBalance} />
      </div>

      {/* Action CTA */}
      <Button className="w-full" size="lg" onClick={onSubmit} disabled={isLoading || selectedSubjects.length === 0}>
        {isLoading ? 'Generating suggested plan...' : 'Calculate Revision Plan'}
      </Button>
    </div>
  )
}
