import { useEffect, useRef, useState, type RefObject } from 'react'

export interface Size {
  readonly width: number
  readonly height: number
}

/** How much to shrink a box of this size so that it fits into its container. Never enlarges. */
export function fitScale(box: Size, container: Size): number {
  if (container.width <= 0 || container.height <= 0) return 1
  return Math.min(1, container.width / box.width, container.height / box.height)
}

/** Watches a container and returns the scale for a box of a fixed size inside it. */
export function useFit(box: Size): { container: RefObject<HTMLDivElement | null>; scale: number } {
  const container = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)

  useEffect(() => {
    const element = container.current
    if (!element) return undefined
    const measure = () =>
      setScale(fitScale(box, { width: element.clientWidth, height: element.clientHeight }))
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    measure()
    return () => observer.disconnect()
  }, [box])

  return { container, scale }
}
