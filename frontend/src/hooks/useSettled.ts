import { useCallback, useEffect, useRef } from 'react'

/** So long a new screen takes no tap: a third quick tap on the old button would press the new one. */
export const SETTLE_MS = 800

/** Tells whether this part of the screen has been there for a moment. */
export function useSettled(): () => boolean {
  const shownAt = useRef(Number.POSITIVE_INFINITY)
  useEffect(() => {
    shownAt.current = performance.now()
  }, [])
  return useCallback(() => performance.now() - shownAt.current >= SETTLE_MS, [])
}
