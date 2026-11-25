import { useEffect, useRef, type RefObject } from 'react'

/** When the control with the focus goes away, the focus moves to the text that replaced it. */
export function useRescueFocus(gone: boolean, target: RefObject<HTMLElement | null>): void {
  const before = useRef(gone)

  useEffect(() => {
    const happened = gone && !before.current
    before.current = gone
    const active = document.activeElement
    const lost = active === null || active === document.body
    if (happened && lost && document.hasFocus()) target.current?.focus()
  }, [gone, target])
}
