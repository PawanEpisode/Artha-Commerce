import { useLastVisitReporter } from '../hooks/useLastVisitReporter'

/** Mounted once in the /app layout. Renders nothing. */
export function LastVisitReporter() {
  useLastVisitReporter()
  return null
}
