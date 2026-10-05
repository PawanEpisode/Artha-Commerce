import {
  BellRing,
  CalendarRange,
  FileClock,
  Flame,
  Layers,
  ListChecks,
  type LucideProps,
  NotebookPen,
  Sparkles,
  StudyTimeIcon,
  Timer,
} from '@artha/design-system'

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
  'study-time': StudyTimeIcon,
  'bell-ring': BellRing,
}

export function FeatureIcon({ name, ...props }: { name: FeatureIconKey } & LucideProps) {
  const Icon = icons[name]
  return <Icon aria-hidden {...props} />
}
