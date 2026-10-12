import { useEffect, useRef, useState } from 'react'

/** True once the element has been on screen (stays true). Without IntersectionObserver it is true straight away. */
export function useInView<T extends Element>() {
  const ref = useRef<T | null>(null)
  const [seen, setSeen] = useState(() => typeof IntersectionObserver === 'undefined')

  useEffect(() => {
    const node = ref.current
    if (seen || !node) return
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setSeen(true)
        observer.disconnect()
      }
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [seen])

  return [ref, seen] as const
}
