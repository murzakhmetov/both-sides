import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'

gsap.registerPlugin(ScrollTrigger)

export { gsap, ScrollTrigger }

let lenis: Lenis | null = null

/** Smooth scrolling. Never for people who ask for less motion. */
export function startSmoothScroll(): () => void {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return () => undefined
  const instance = new Lenis({ lerp: 0.11 })
  const onFrame = (time: number) => instance.raf(time * 1000)
  instance.on('scroll', ScrollTrigger.update)
  gsap.ticker.add(onFrame)
  gsap.ticker.lagSmoothing(0)
  lenis = instance
  return () => {
    gsap.ticker.remove(onFrame)
    instance.destroy()
    lenis = null
  }
}

/** Goes to a section and moves the keyboard focus there. */
export function scrollToId(id: string): void {
  const target = document.getElementById(id)
  if (!target) return
  if (lenis) lenis.scrollTo(target)
  else target.scrollIntoView()
  target.focus({ preventScroll: true })
}
