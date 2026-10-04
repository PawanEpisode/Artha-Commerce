import { brand, OTP_EXPIRY_MINUTES } from './brand'

export interface EmailContent {
  /** Hidden preview text shown by inbox lists. */
  preheader: string
  heading: string
  /** Paragraphs (plain text; may contain Supabase template variables). */
  body: string[]
  button?: { label: string; url: string }
  /** Shows the one-time code box. `{{ .Token }}` is added by the layout. */
  code?: { intro: string }
  /** Small print under the button/code. */
  note?: string
  /** Why the recipient got this email. */
  reason: string
}

const font = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"

/** Bulletproof table layout: works in Gmail, Outlook, Apple Mail and on phones. Inline styles only (plus one dark-mode block). */
export function renderEmail(c: EmailContent): string {
  const l = brand.light
  const paragraphs = c.body
    .map((p) => `<p class="text" style="margin:0 0 16px;font-size:16px;line-height:26px;color:${l.text};">${p}</p>`)
    .join('\n              ')

  const button = c.button
    ? `<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:8px 0 24px;">
                <tr>
                  <td class="btn" bgcolor="${l.primary}" style="border-radius:10px;background:${l.primary};">
                    <a href="${c.button.url}" class="btn-link" style="display:inline-block;padding:14px 28px;font-size:16px;font-weight:700;line-height:20px;color:${l.onPrimary};text-decoration:none;border-radius:10px;">${c.button.label}</a>
                  </td>
                </tr>
              </table>
              <p class="muted" style="margin:0 0 24px;font-size:13px;line-height:20px;color:${l.muted};">Button not working? Copy this link into your browser:<br><a href="${c.button.url}" class="link" style="color:${l.primary};word-break:break-all;">${c.button.url}</a></p>`
    : ''

  const code = c.code
    ? `<p class="text" style="margin:0 0 8px;font-size:16px;line-height:26px;color:${l.text};">${c.code.intro}</p>
              <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 8px;">
                <tr>
                  <td class="code" bgcolor="${l.codeBg}" style="border-radius:10px;background:${l.codeBg};padding:14px 24px;">
                    <span class="text" style="font-family:'SFMono-Regular',Menlo,Consolas,monospace;font-size:30px;line-height:36px;letter-spacing:8px;font-weight:700;color:${l.text};">{{ .Token }}</span>
                  </td>
                </tr>
              </table>
              <p class="muted" style="margin:0 0 24px;font-size:13px;line-height:20px;color:${l.muted};">Never share this code with anyone. We will never ask for it.</p>`
    : ''

  const note = c.note
    ? `<p class="muted" style="margin:0 0 8px;font-size:13px;line-height:20px;color:${l.muted};">${c.note}</p>`
    : ''

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>${c.heading}</title>
  <style>
    @media (prefers-color-scheme: dark) {
      .page { background: ${brand.dark.page} !important; }
      .card { background: ${brand.dark.card} !important; border-color: ${brand.dark.border} !important; }
      .text { color: ${brand.dark.text} !important; }
      .muted { color: ${brand.dark.muted} !important; }
      .link { color: ${brand.dark.primary} !important; }
      .btn { background: ${brand.dark.primary} !important; }
      .btn-link { color: ${brand.dark.onPrimary} !important; }
      .code { background: ${brand.dark.codeBg} !important; }
    }
    @media only screen and (max-width: 520px) {
      .inner { padding: 28px 20px !important; }
    }
  </style>
</head>
<body class="page" style="margin:0;padding:0;background:${l.page};font-family:${font};">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">${c.preheader}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" class="page" style="background:${l.page};">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;">
          <tr>
            <td style="padding:0 4px 20px;">
              <span class="text" style="font-size:20px;font-weight:800;letter-spacing:-0.3px;color:${l.text};">${brand.name}</span>
            </td>
          </tr>
          <tr>
            <td class="card" style="background:${l.card};border:1px solid ${l.border};border-radius:16px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td class="inner" style="padding:36px 36px 28px;">
              <h1 class="text" style="margin:0 0 16px;font-size:24px;line-height:32px;font-weight:800;color:${l.text};">${c.heading}</h1>
              ${paragraphs}
              ${button}
              ${code}
              ${note}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 8px 0;">
              <p class="muted" style="margin:0 0 6px;font-size:12px;line-height:18px;color:${l.muted};">${c.reason}</p>
              <p class="muted" style="margin:0;font-size:12px;line-height:18px;color:${l.muted};">${brand.name}. ${brand.tagline}.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
`
}

export const EXPIRY_NOTE = `The link and code expire in ${OTP_EXPIRY_MINUTES} minutes and work only once.`
