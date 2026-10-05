import * as React from 'react'

import { LoaderCircle } from '../../icons'
import type { PixelCrop } from '../../lib/image'
import { Alert } from './alert'
import { Button } from './button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './dialog'
import { Slider } from './slider'

// Loaded on demand: the cropper (react-easy-crop) is not part of the main bundle.
const Cropper = React.lazy(() => import('react-easy-crop'))

export interface ImageCropDialogProps {
  open: boolean
  /** Object URL of the chosen photo. */
  imageUrl: string | null
  /** Called with the chosen square in source pixels. The caller draws and uploads it. `zoom` is for analytics only. */
  onSave: (crop: PixelCrop, zoom: number) => void
  onCancel: () => void
  saving?: boolean
  /** 0 to 100 while uploading, or null. */
  progress?: number | null
  /** Shown above the buttons. The crop is kept, so Save works as Retry. */
  error?: string | null
}

const MIN_ZOOM = 1
const MAX_ZOOM = 3

/**
 * Square crop with a round preview, drag, a zoom slider and arrow keys. While saving, Save is disabled and focus stays
 * in the dialog; Cancel is still allowed (the caller aborts the request).
 */
export function ImageCropDialog({ open, imageUrl, onSave, onCancel, saving, progress, error }: ImageCropDialogProps) {
  const [crop, setCrop] = React.useState({ x: 0, y: 0 })
  const [zoom, setZoom] = React.useState(1)
  const area = React.useRef<PixelCrop | null>(null)

  React.useEffect(() => {
    if (open) {
      setCrop({ x: 0, y: 0 })
      setZoom(1)
      area.current = null
    }
  }, [open, imageUrl])

  return (
    <Dialog open={open} onOpenChange={(next) => (!next ? onCancel() : undefined)}>
      <DialogContent aria-describedby="crop-help">
        <DialogTitle>Adjust your photo</DialogTitle>
        <DialogDescription id="crop-help">
          Drag to move, use the slider to zoom, or focus the picture and use the arrow keys.
        </DialogDescription>

        <div className="relative mt-4 aspect-square w-full overflow-hidden rounded-xl bg-muted">
          <React.Suspense
            fallback={
              <div className="grid h-full place-items-center text-muted-foreground" role="status">
                <LoaderCircle className="size-6 animate-spin motion-reduce:animate-none" aria-hidden />
                <span className="sr-only">Preparing your photo</span>
              </div>
            }
          >
            {imageUrl ? (
              <Cropper
                image={imageUrl}
                crop={crop}
                zoom={zoom}
                aspect={1}
                cropShape="round"
                showGrid={false}
                minZoom={MIN_ZOOM}
                maxZoom={MAX_ZOOM}
                onCropChange={setCrop}
                onZoomChange={setZoom}
                onCropComplete={(_, pixels) => {
                  area.current = pixels
                }}
              />
            ) : null}
          </React.Suspense>
        </div>

        <div className="mt-3">
          <Slider
            label="Zoom"
            value={zoom}
            min={MIN_ZOOM}
            max={MAX_ZOOM}
            step={0.05}
            onValueChange={setZoom}
            disabled={saving}
          />
        </div>

        {saving ? (
          <div
            role="progressbar"
            aria-label="Uploading your photo"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress ?? undefined}
            className="mt-2 h-2 overflow-hidden rounded-full bg-secondary"
          >
            <div
              className="h-full bg-primary transition-[width] motion-reduce:transition-none"
              style={{ width: `${progress ?? 40}%` }}
            />
          </div>
        ) : null}

        {error ? (
          <Alert variant="error" className="mt-3">
            {error}
          </Alert>
        ) : null}

        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            disabled={saving || !imageUrl}
            onClick={() => (area.current ? onSave(area.current, zoom) : undefined)}
            aria-busy={saving || undefined}
          >
            {saving ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
            {error ? 'Try again' : 'Save photo'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
