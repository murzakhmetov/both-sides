import { useEffect, useLayoutEffect, useRef, type RefObject } from 'react'

/** Below this the words in the drawing would be too small to read. */
const SMALLEST = 0.66

function inner(element: HTMLElement): number {
  const style = getComputedStyle(element)
  return element.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)
}

/**
 * Draws the things marked with data-fit inside an area smaller when the window is too low for them
 * (--fit, used as zoom). Once smaller, they stay so until the window or the language changes:
 * nothing jumps between the steps.
 */
export function useFit(area: RefObject<HTMLElement | null>, step: string, lang: string): void {
  const fit = useRef(1)

  const measure = useRef(() => {
    const element = area.current
    if (!element) return
    element.style.setProperty('--fit', '1')
    const items = [...element.querySelectorAll<HTMLElement>('[data-fit]')]
    const wanted = Math.max(1, ...items.map((item) => item.offsetHeight))
    fit.current = Math.max(SMALLEST, Math.min(fit.current, inner(element) / wanted))
    element.style.setProperty('--fit', fit.current.toFixed(3))
  })

  useLayoutEffect(() => measure.current(), [step])

  useEffect(() => {
    const again = () => {
      fit.current = 1
      measure.current()
    }
    again()
    window.addEventListener('resize', again)
    void document.fonts.ready.then(again)
    return () => window.removeEventListener('resize', again)
  }, [lang])
}
