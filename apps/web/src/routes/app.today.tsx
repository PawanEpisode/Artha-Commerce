import { createFileRoute, Outlet } from '@tanstack/react-router'

/** Layout for `/app/today` (the day) and `/app/today/$date` (a preview or a recap). */
export const Route = createFileRoute('/app/today')({ component: Outlet })
