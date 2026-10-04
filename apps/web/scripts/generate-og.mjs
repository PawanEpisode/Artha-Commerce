// Generates the 1200x630 social preview (WhatsApp/LinkedIn/X) and the app icon.
// Run: pnpm --filter @artha/web og   (output is committed; re-run when branding changes)
import sharp from 'sharp'
import { writeFileSync } from 'node:fs'

const og = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1b1747"/><stop offset="1" stop-color="#4a3fd6"/></linearGradient>
    <radialGradient id="g1" cx="0.85" cy="0.1" r="0.6"><stop offset="0" stop-color="#2fd39a" stop-opacity="0.45"/><stop offset="1" stop-color="#2fd39a" stop-opacity="0"/></radialGradient>
    <radialGradient id="g2" cx="0.1" cy="1" r="0.5"><stop offset="0" stop-color="#f5b83d" stop-opacity="0.4"/><stop offset="1" stop-color="#f5b83d" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/><rect width="1200" height="630" fill="url(#g1)"/><rect width="1200" height="630" fill="url(#g2)"/>
  <rect x="80" y="80" width="72" height="72" rx="20" fill="#fff"/>
  <path d="M100 135 116 98l16 37" fill="none" stroke="#4a3fd6" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M106 124h20" stroke="#f5b83d" stroke-width="6" stroke-linecap="round"/>
  <text x="172" y="130" font-family="Helvetica, Arial, sans-serif" font-size="40" font-weight="700" fill="#fff">ArthaCommerce</text>
  <text x="80" y="330" font-family="Helvetica, Arial, sans-serif" font-size="78" font-weight="800" fill="#fff">Your entire exam prep,</text>
  <text x="80" y="420" font-family="Helvetica, Arial, sans-serif" font-size="78" font-weight="800" fill="#7ef0c6">in one calm workspace.</text>
  <text x="80" y="520" font-family="Helvetica, Arial, sans-serif" font-size="34" fill="#d9d6ff">Study planner · Mock tests · AI doubt solver</text>
  <text x="80" y="566" font-family="Helvetica, Arial, sans-serif" font-size="30" fill="#b8b3f5">For CA, CS and CMA students</text>
</svg>`

await sharp(Buffer.from(og)).png({ compressionLevel: 9, palette: true }).toFile('public/og/default.png')

const icon = `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 32 32"><rect width="32" height="32" rx="9" fill="#4a3fd6"/><path d="M9 22 16 8l7 14" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 18h8" stroke="#f5b83d" stroke-width="2.6" stroke-linecap="round"/></svg>`
await sharp(Buffer.from(icon)).png().toFile('public/icon-512.png')
writeFileSync('public/.gitkeep', '')
console.log('OG image and icon generated')
