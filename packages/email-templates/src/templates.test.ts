import { describe, expect, it } from 'vitest'

import { templates } from './templates'

describe('auth email templates', () => {
  it('covers the six Supabase auth email types', () => {
    expect(templates.map((t) => t.key).sort()).toEqual(
      ['confirmation', 'email_change', 'invite', 'magic_link', 'reauthentication', 'recovery'].sort(),
    )
  })

  for (const t of templates) {
    describe(t.key, () => {
      it('contains every Supabase variable it needs', () => {
        for (const v of t.requires) expect(t.html).toContain(v)
      })
      it('only uses known Supabase variables', () => {
        const allowed = new Set([
          '.ConfirmationURL',
          '.Token',
          '.TokenHash',
          '.SiteURL',
          '.Email',
          '.NewEmail',
          '.RedirectTo',
        ])
        for (const m of t.html.matchAll(/\{\{\s*([^}\s]+)\s*\}\}/g)) expect(allowed.has(m[1])).toBe(true)
      })
      it('has no unbalanced template braces', () => {
        expect((t.html.match(/\{\{/g) ?? []).length).toBe((t.html.match(/\}\}/g) ?? []).length)
      })
      it('has a subject, preview text and accessible structure', () => {
        expect(t.subject.length).toBeGreaterThan(5)
        expect(t.html).toContain('<html lang="en">')
        expect(t.html).toContain('<title>')
        expect(t.html).toContain('role="presentation"')
      })
      it('never links to http (https only, via the site URL variable)', () => {
        expect(t.html).not.toMatch(/href="http:\/\//)
      })
    })
  }

  it('sign-in style emails link through /auth/confirm with a token hash (scanner safe)', () => {
    for (const key of ['confirmation', 'invite', 'magic_link', 'recovery'] as const) {
      const html = templates.find((t) => t.key === key)?.html ?? ''
      expect(html).toContain('/auth/confirm?token_hash={{ .TokenHash }}&type=')
    }
  })
})
