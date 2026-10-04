import { Container } from '@artha/design-system'
import type { ReactNode } from 'react'

/** Centres an auth card on the page; keeps padding comfortable from 320 px phones to desktop. */
export function AuthPage({ children }: { children: ReactNode }) {
  return <Container className="grid min-h-[70vh] place-items-center py-10 sm:py-16">{children}</Container>
}
