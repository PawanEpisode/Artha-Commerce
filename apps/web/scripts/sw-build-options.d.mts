import type { BuildOptions } from 'esbuild'

export function swBuildOptions(options?: {
  version?: string
  vapidPublicKey?: string
  apiBaseUrl?: string
  outfile?: string
  write?: boolean
}): BuildOptions
export function swVersionFrom(env: Record<string, string | undefined>): string
