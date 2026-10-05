import { Clock, ListChecks, type LucideIcon, Settings, Timer } from '@artha/design-system'

import type { WorkspaceLink } from './workspace-nav'

const ICONS: Record<WorkspaceLink['to'], LucideIcon> = {
  '/app/focus': Timer,
  '/app/tracker': Clock,
  '/app/syllabus': ListChecks,
  '/app/settings/focus': Timer,
  '/app/settings/tracker': Clock,
  '/app/settings/coverage': ListChecks,
  '/app/account': Settings,
}

export const workspaceIcon = (to: WorkspaceLink['to']): LucideIcon => ICONS[to]
