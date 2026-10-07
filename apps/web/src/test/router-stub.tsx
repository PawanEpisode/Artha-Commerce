import type { ReactNode } from 'react'

/**
 * A stand-in for `@tanstack/react-router` in component tests: `Link` becomes an anchor whose href shows the route and
 * its params, so a test can assert where a link goes without mounting a router.
 * Use: `vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)`.
 */
function Link({
  to,
  params,
  search,
  children,
  ...rest
}: {
  to: string
  params?: Record<string, string>
  search?: Record<string, unknown>
  children?: ReactNode
  [key: string]: unknown
}) {
  let href = to
  for (const [key, value] of Object.entries(params ?? {})) href = href.replace(`$${key}`, value)
  const query = new URLSearchParams(
    Object.entries(search ?? {}).filter(([, v]) => v !== undefined) as Array<[string, string]>,
  ).toString()
  const { asChild: _asChild, ...anchor } = rest
  return (
    <a href={query ? `${href}?${query}` : href} {...(anchor as object)}>
      {children}
    </a>
  )
}

export const routerStub = {
  Link,
  useRouterState: ({ select }: { select: (s: { location: { pathname: string } }) => unknown }) =>
    select({ location: { pathname: '/app/notes' } }),
  useNavigate: () => () => Promise.resolve(),
}
