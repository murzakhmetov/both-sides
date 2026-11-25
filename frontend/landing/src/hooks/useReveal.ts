import { useEffect, type RefObject } from 'react'
import { gsap } from '../scroll'
import { useReducedMotion } from './useMediaQuery'

const STEP_SECONDS = 0.14

/**
 * Every element with data-reveal inside the section fades in with a slight upward drift, once.
 * Only its opacity changes: the keyboard can reach a button before it is on screen, and that scrolls it there.
 */
export function useReveal(ref: RefObject<HTMLElement | null>): void {
  const still = useReducedMotion()
  useEffect(() => {
    const root = ref.current
    if (!root || still) return undefined
    const context = gsap.context(() => {
      for (const item of gsap.utils.toArray<HTMLElement>('[data-reveal]')) {
        gsap.fromTo(
          item,
          { opacity: 0, y: 28 },
          {
            opacity: 1,
            y: 0,
            duration: 1.1,
            ease: 'power2.out',
            delay: Number(item.dataset['reveal'] ?? 0) * STEP_SECONDS,
            scrollTrigger: { trigger: item, start: 'top 88%', once: true },
          },
        )
      }
    }, root)
    return () => context.revert()
  }, [ref, still])
}
