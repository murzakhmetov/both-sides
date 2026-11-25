import { useEffect, useState, type RefObject } from 'react'
import { ScrollTrigger } from '../scroll'

interface Range {
  readonly start: string
  readonly end: string
}

/** The section crosses the middle of the window. Never two sections at once, so a turn back is noticed too. */
const MIDDLE: Range = { start: 'top center', end: 'bottom center' }

/** The section is less than one window away. */
export const SOON: Range = { start: 'top 200%', end: 'bottom -100%' }

/** True while the section is inside the range. */
export function useInView(ref: RefObject<HTMLElement | null>, range: Range = MIDDLE): boolean {
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const trigger = ScrollTrigger.create({
      trigger: ref.current,
      start: range.start,
      end: range.end,
      onToggle: (self) => setInView(self.isActive),
    })
    setInView(trigger.isActive)
    return () => trigger.kill()
  }, [ref, range])
  return inView
}
