import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ImagePickerDialog, imageProblem } from './ImagePickerDialog'

const png = (name = 'a.png', size = 1000) => new File([new Uint8Array(size)], name, { type: 'image/png' })

describe('imageProblem', () => {
  it('accepts PNG, JPEG and WebP up to 10 MB and says why otherwise', () => {
    expect(imageProblem({ type: 'image/png', size: 5 })).toBeNull()
    expect(imageProblem({ type: 'image/webp', size: 5 })).toBeNull()
    expect(imageProblem({ type: 'image/gif', size: 5 })).toMatch(/PNG, JPEG or WebP/)
    expect(imageProblem({ type: 'image/png', size: 11 * 1024 * 1024 })).toMatch(/10 MB/)
  })
})

describe('ImagePickerDialog', () => {
  it('needs a file and a description, or an explicit "decoration" choice', async () => {
    const onSubmit = vi.fn()
    render(<ImagePickerDialog open onOpenChange={() => undefined} busy={false} onSubmit={onSubmit} />)
    const add = screen.getByRole('button', { name: 'Add image' })
    expect(add).toBeDisabled()
    await userEvent.upload(screen.getByLabelText('Image file'), png())
    expect(add).toBeDisabled()
    expect(screen.getByText(/Add a description, or tick/)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Description (alt text)'), 'Journal entry')
    expect(add).toBeEnabled()
    await userEvent.click(add)
    expect(onSubmit).toHaveBeenCalledWith(expect.any(File), 'Journal entry')
  })

  it('lets a decorative image through with empty alt text', async () => {
    const onSubmit = vi.fn()
    render(<ImagePickerDialog open onOpenChange={() => undefined} busy={false} onSubmit={onSubmit} />)
    await userEvent.upload(screen.getByLabelText('Image file'), png())
    await userEvent.click(screen.getByLabelText('This image is only decoration'))
    expect(screen.getByLabelText('Description (alt text)')).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Add image' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.any(File), '')
  })

  it('refuses a file of the wrong type with a message', async () => {
    render(<ImagePickerDialog open onOpenChange={() => undefined} busy={false} onSubmit={() => undefined} />)
    await userEvent.upload(screen.getByLabelText('Image file'), new File(['x'], 'a.gif', { type: 'image/gif' }), {
      applyAccept: false,
    })
    expect(screen.getByRole('alert')).toHaveTextContent('Choose a PNG, JPEG or WebP image.')
    expect(screen.getByRole('button', { name: 'Add image' })).toBeDisabled()
  })

  it('shows an upload error and a busy label', () => {
    render(
      <ImagePickerDialog
        open
        onOpenChange={() => undefined}
        busy
        error="The image could not be uploaded."
        onSubmit={() => undefined}
      />,
    )
    expect(screen.getByText('The image could not be uploaded.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Uploading…' })).toBeDisabled()
  })
})
