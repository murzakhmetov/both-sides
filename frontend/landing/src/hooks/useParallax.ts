import { useEffect, type RefObject } from 'react'
import { gsap } from '../scroll'
import { useMediaQuery } from './useMediaQuery'

/** How far things move at the edge of the window, in pixels. The picture is 12 px larger than the window. */
const PICTURE_SHIFT = -10
const CARD_SHIFT = 7

const DESKTOP = '(hover: hover) and (pointer: fine) and (min-width: 64rem) and (prefers-reduced-motion: no-preference)'

/** A function that moves an element slowly; x and y run from -1 to 1. */
function mover(element: HTMLElement, shift: number): (x: number, y: number) => void {
  const toX = gsap.quickTo(element, 'x', { duration: 1.3, ease: 'power2.out' })
  const toY = gsap.quickTo(element, 'y', { duration: 1.3, ease: 'power2.out' })
  return (x, y) => {
    toX(x * shift)
    toY(y * shift)
  }
}

/**
 * Desktop only: the picture moves a little against the mouse, cards marked with
 * data-float a little with it. Never for touch or for people who ask for less motion.
 */
export function useParallax(picture: RefObject<HTMLElement | null>): void {
  const allowed = useMediaQuery(DESKTOP)
  useEffect(() => {
    const layer = picture.current
    if (!allowed || !layer) return undefined
    const cards = gsap.utils.toArray<HTMLElement>('[data-float]')
    const moves = [mover(layer, PICTURE_SHIFT), ...cards.map((card) => mover(card, CARD_SHIFT))]

    const onMove = (event: PointerEvent) => {
      const x = (event.clientX / window.innerWidth) * 2 - 1
      const y = (event.clientY / window.innerHeight) * 2 - 1
      for (const move of moves) move(x, y)
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => {
      window.removeEventListener('pointermove', onMove)
      gsap.killTweensOf([layer, ...cards])
      gsap.set([layer, ...cards], { clearProps: 'transform' })
    }
  }, [allowed, picture])
}
