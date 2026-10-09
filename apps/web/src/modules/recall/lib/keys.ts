import type { QueueSource } from './api'

export const recallKeys = {
  all: ['recall'] as const,
  today: ['recall', 'today'] as const,
  queue: (source: QueueSource, params: object = {}) => ['recall', 'queue', source, params] as const,
  pack: ['recall', 'pack'] as const,
  settings: ['recall', 'settings'] as const,
  forgotten: (params: object = {}) => ['recall', 'forgotten', params] as const,
  stats: (report: string, params: object = {}) => ['recall', 'stats', report, params] as const,
  cards: (params: object = {}) => ['recall', 'cards', params] as const,
  card: (id: string) => ['recall', 'card', id] as const,
  cardHistory: (id: string) => ['recall', 'card', id, 'history'] as const,
  offline: ['recall', 'offline'] as const,
  summary: (sessionId: string) => ['recall', 'summary', sessionId] as const,
}
