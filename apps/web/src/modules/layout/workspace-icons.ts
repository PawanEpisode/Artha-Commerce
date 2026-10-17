import {
  Bell,
  BookOpen,
  CalendarClock,
  Clock,
  FileClock,
  FileText,
  Inbox,
  Layers,
  ListChecks,
  type LucideIcon,
  Notebook,
  PenLine,
  RefreshCw,
  Settings,
  Target,
  Timer,
  TrendingUp,
} from '@artha/design-system'

import type { WorkspaceLink } from './workspace-nav'

const ICONS: Record<WorkspaceLink['to'], LucideIcon> = {
  '/app/revision': RefreshCw,
  '/app/practice': PenLine,
  '/app/notifications': Inbox,
  '/app/settings/recall': Layers,
  '/app/today': CalendarClock,
  '/app/planner': Target,
  '/app/focus': Timer,
  '/app/tracker': Clock,
  '/app/syllabus': ListChecks,
  '/app/notes': Notebook,
  '/app/recall': Layers,
  '/app/questions': FileText,
  '/app/pyq': FileClock,
  '/app/mcq': BookOpen,
  '/app/analytics': TrendingUp,
  '/app/settings/today': CalendarClock,
  '/app/settings/focus': Timer,
  '/app/settings/tracker': Clock,
  '/app/settings/coverage': ListChecks,
  '/app/settings/notes': Notebook,
  '/app/settings/notifications': Bell,
  '/app/account': Settings,
}

export const workspaceIcon = (to: WorkspaceLink['to']): LucideIcon => ICONS[to]
