import { useEffect, useState } from 'react'

/** The inner size of this window, following the student resizing it. Zero while rendering on the server. */
export function useWindowSize() {
  const read = () => ({
    width: typeof window === 'undefined' ? 0 : window.innerWidth,
    height: typeof window === 'undefined' ? 0 : window.innerHeight,
  })
  const [size, setSize] = useState(read)
  useEffect(() => {
    const onResize = () => setSize(read())
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return size
}
