import { BellRing, CalendarRange, FileClock, Flame, Layers, ListChecks, NotebookPen, Sparkles, Timer, type LucideProps } from 'lucide-react'
import type { FeatureIconKey } from '~/modules/catalog'

const icons: Record<FeatureIconKey, React.ComponentType<LucideProps>> = {
  calendar: CalendarRange,
  'list-checks': ListChecks,
  timer: Timer,
  sparkles: Sparkles,
  'notebook-pen': NotebookPen,
  layers: Layers,
  'file-clock': FileClock,
  flame: Flame,
  'bell-ring': BellRing,
}

export function FeatureIcon({ name, ...props }: { name: FeatureIconKey } & LucideProps) {
  const Icon = icons[name]
  return <Icon aria-hidden {...props} />
}
