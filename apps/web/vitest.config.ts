import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vitest/config'

// Unit tests only need TypeScript path aliases, not the TanStack Start / Nitro build plugins.
// Pure logic (*.test.ts) runs in node. Component tests (*.test.tsx) run in jsdom with Testing Library.
export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    projects: [
      {
        extends: true,
        test: { name: 'logic', environment: 'node', include: ['src/**/*.test.ts'] },
      },
      {
        extends: true,
        test: {
          name: 'components',
          environment: 'jsdom',
          include: ['src/**/*.test.tsx'],
          setupFiles: ['./src/test/setup-dom.ts'],
          alias: { 'canvas-confetti': fileURLToPath(new URL('./src/test/confetti-stub.ts', import.meta.url)) },
        },
      },
    ],
  },
})
