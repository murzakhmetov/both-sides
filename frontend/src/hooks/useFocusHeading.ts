import { useEffect, useRef, type RefObject } from 'react'

/**
 * A new screen starts at its top, and the focus moves to its heading, so that a keyboard or
 * screen-reader user is not thrown back to the start of the page.
 */
export function useFocusHeading(screen: string): RefObject<HTMLElement | null> {
  const area = useRef<HTMLElement>(null)
  const previous = useRef(screen)

  useEffect(() => {
    const before = previous.current
    previous.current = screen
    if (before === '' || before === screen) return
    window.scrollTo(0, 0)
    // Never take the focus out of another frame of the demo page.
    if (!document.hasFocus()) return
    const active = document.activeElement
    const lost = active === null || active === document.body || area.current?.contains(active)
    if (!lost) return
    const heading = area.current?.querySelector<HTMLElement>('h1')
    heading?.setAttribute('tabindex', '-1')
    heading?.focus({ preventScroll: true })
  }, [screen])

  return area
}
