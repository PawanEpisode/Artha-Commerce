export const notificationKeys = {
  all: ['notifications'] as const,
  settings: ['notifications', 'settings'] as const,
  categories: ['notifications', 'categories'] as const,
  devices: ['notifications', 'devices'] as const,
  /** Prefix of everything the bell and the inbox page show; invalidating it refreshes both. */
  inbox: ['notifications', 'inbox'] as const,
  bell: ['notifications', 'inbox', 'bell'] as const,
  thought: ['notifications', 'thought'] as const,
  inboxList: ['notifications', 'inbox', 'list'] as const,
}
