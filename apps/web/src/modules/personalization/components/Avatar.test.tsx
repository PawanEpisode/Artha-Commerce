import { Avatar, AvatarPicker } from '@artha/design-system'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

describe('Avatar', () => {
  it('shows initials from the name, with no image request', () => {
    const { container } = render(<Avatar name="Aarav Mehta" seed="u1" />)
    expect(screen.getByRole('img', { name: 'Aarav Mehta' })).toHaveTextContent('AM')
    expect(container.querySelector('img')).toBeNull()
  })

  it('falls back to the email, then a placeholder, when there is no name', () => {
    const { rerender } = render(<Avatar email="zed@example.com" />)
    expect(screen.getByRole('img', { name: 'Profile picture' })).toHaveTextContent('Z')
    rerender(<Avatar />)
    expect(screen.getByRole('img')).toHaveTextContent('?')
  })

  it('keeps the same colour when the name changes (it follows the user id)', () => {
    const { rerender } = render(<Avatar name="Aarav" seed="same-user" />)
    const before = screen.getByRole('img').getAttribute('style')
    rerender(<Avatar name="Completely Different" seed="same-user" />)
    expect(screen.getByRole('img').getAttribute('style')).toBe(before)
  })

  it('uses the small rendition up to 44 px and the large one at 96 px', () => {
    const urls = { small: 'https://x/s-128.webp', large: 'https://x/l-512.webp' }
    const { container, rerender } = render(<Avatar name="A B" urls={urls} size={44} />)
    expect(container.querySelector('img')).toHaveAttribute('src', urls.small)
    rerender(<Avatar name="A B" urls={urls} size={96} />)
    expect(container.querySelector('img')).toHaveAttribute('src', urls.large)
  })

  it('drops to initials when the photo fails to load, with no broken image left', () => {
    const { container } = render(
      <Avatar name="Aarav Mehta" urls={{ small: 'https://x/a.webp', large: 'https://x/b.webp' }} />,
    )
    fireEvent.error(container.querySelector('img') as HTMLImageElement)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByRole('img', { name: 'Aarav Mehta' })).toHaveTextContent('AM')
  })

  it('draws a preset by key, and ignores an unknown key', () => {
    const { container, rerender } = render(<Avatar name="A B" presetKey="p07" />)
    expect(container.querySelector('svg')).not.toBeNull()
    expect(container.querySelector('[data-kind="preset"]')).not.toBeNull()
    rerender(<Avatar name="A B" presetKey="p99" />)
    expect(container.querySelector('svg')).toBeNull()
  })

  it('a photo wins over a preset', () => {
    const { container } = render(<Avatar presetKey="p01" urls={{ small: 's', large: 'l' }} />)
    expect(container.querySelector('[data-kind="photo"]')).not.toBeNull()
  })

  it('renders a fixed-size placeholder while loading and can be decorative', () => {
    const { container, rerender } = render(<Avatar loading size={96} />)
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true')
    expect(container.firstElementChild?.className).toContain('size-24')
    rerender(<Avatar name="A B" decorative />)
    expect(screen.queryByRole('img')).toBeNull()
  })
})

describe('AvatarPicker', () => {
  const base = { presetKey: null, hasPhoto: false, uploadEnabled: true, onFile: vi.fn(), onPreset: vi.fn() }

  it('offers upload first, and presets on the other tab', async () => {
    const onPreset = vi.fn()
    render(<AvatarPicker {...base} onPreset={onPreset} />)
    expect(screen.getByRole('button', { name: 'Add a photo' })).toBeEnabled()
    await userEvent.click(screen.getByRole('tab', { name: 'Avatars' }))
    expect(screen.getAllByRole('button', { name: /^Avatar \d+: / })).toHaveLength(24)
    await userEvent.click(screen.getByRole('button', { name: 'Avatar 3: Peaks' }))
    expect(onPreset).toHaveBeenCalledWith('p03')
  })

  it('marks the stored preset as pressed', async () => {
    render(<AvatarPicker {...base} presetKey="p03" />)
    await userEvent.click(screen.getByRole('tab', { name: 'Avatars' }))
    expect(screen.getByRole('button', { name: 'Avatar 3: Peaks' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('shows presets only when upload is off', () => {
    render(<AvatarPicker {...base} uploadEnabled={false} />)
    expect(screen.queryByRole('tab')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Add a photo' })).toBeNull()
    expect(screen.getAllByRole('button', { name: /^Avatar \d+: / })).toHaveLength(24)
  })

  it('says why upload is unavailable, and disables it', () => {
    render(<AvatarPicker {...base} uploadDisabledReason="Photo upload needs a connection." />)
    expect(screen.getByRole('button', { name: 'Add a photo' })).toBeDisabled()
    expect(screen.getByText('Photo upload needs a connection.')).toBeInTheDocument()
  })

  it('offers replace and remove when there is a photo, and announces file errors', async () => {
    const onRemove = vi.fn()
    render(<AvatarPicker {...base} hasPhoto onRemove={onRemove} fileError="Use a JPG, PNG or WebP image." />)
    expect(screen.getByRole('button', { name: 'Replace photo' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remove photo' }))
    expect(onRemove).toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('Use a JPG, PNG or WebP image.')
  })

  it('hands the chosen file to the container', async () => {
    const onFile = vi.fn()
    const { container } = render(<AvatarPicker {...base} onFile={onFile} />)
    const file = new File(['x'], 'me.png', { type: 'image/png' })
    await userEvent.upload(container.querySelector('input[type="file"]') as HTMLInputElement, file)
    expect(onFile).toHaveBeenCalledWith(file)
  })
})
