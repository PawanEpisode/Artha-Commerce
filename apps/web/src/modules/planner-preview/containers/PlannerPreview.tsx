import { PlannerPreviewView } from '../components/PlannerPreviewView'
import { usePlannerPreview } from '../hooks/usePlannerPreview'

export function PlannerPreview() {
  const p = usePlannerPreview()
  return (
    <PlannerPreviewView
      course={p.course}
      level={p.level}
      levelIndex={p.levelIndex}
      plan={p.plan}
      months={p.months}
      hoursPerDay={p.hoursPerDay}
      onCourse={p.selectCourse}
      onLevel={p.setLevelIndex}
      onMonths={p.setMonths}
      onHours={p.setHoursPerDay}
    />
  )
}
