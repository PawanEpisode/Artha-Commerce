import { defineConfig } from 'vitest/config'

// Unit tests only need TypeScript path aliases, not the TanStack Start / Nitro build plugins.
export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: { environment: 'node', include: ['src/**/*.test.{ts,tsx}'] },
})
