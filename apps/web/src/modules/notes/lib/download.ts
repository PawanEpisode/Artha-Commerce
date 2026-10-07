/** Starts a download (or opens a signed file) from a URL the API signed. A hidden link, so no pop-up blocker is involved. */
export function openSignedUrl(url: string, filename?: string) {
  const link = document.createElement('a')
  link.href = url
  link.rel = 'noopener'
  if (filename) link.download = filename
  link.target = '_blank'
  document.body.append(link)
  link.click()
  link.remove()
}
