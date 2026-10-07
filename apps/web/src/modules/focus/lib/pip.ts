/**
 * Floating timer support (X-01 PRD B). Only the detection lives here for now; the window itself arrives with the
 * pop-out wave. Safe to call during server rendering.
 */
export const isDocumentPipSupported = (): boolean =>
  typeof window !== 'undefined' && 'documentPictureInPicture' in window
