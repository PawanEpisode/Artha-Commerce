export const todayKeys = {
  all: ['today'] as const,
  plan: ['today', 'plan'] as const,
  settings: ['today', 'settings'] as const,
  preview: (date: string) => ['today', 'preview', date] as const,
  day: (date: string) => ['today', 'day', date] as const,
}
