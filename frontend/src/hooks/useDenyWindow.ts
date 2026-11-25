import { useEffect, useRef, useState } from 'react'
import type { PhoneView } from '../api/types'

export interface DenyWindow {
  /** Changes with every new first tap, so that the bar starts again. */
  readonly id: number
  readonly seconds: number
}

/**
 * When the window closes, on the clock of performance.now(). The server says how much is
 * left, the reply takes a while, so the time is counted from when the request was sent.
 * A later reply may only shorten a window that is still open.
 */
export function windowEnd(open: number, now: number, askedAt: number, seconds: number): number {
  const end = askedAt + seconds * 1000
  return open > now ? Math.min(open, end) : end
}

/**
 * The time left for the second tap on "I do not know this person". Counted on the phone
 * itself, so that the hint never outlives the server's window, even without a connection.
 */
export function useDenyWindow(view: PhoneView | null, askedAt: number): DenyWindow | null {
  const [shown, setShown] = useState<DenyWindow | null>(null)
  const end = useRef(0)
  const seconds = view?.deny_armed_seconds ?? 0

  useEffect(() => {
    const now = performance.now()
    const before = end.current
    end.current = seconds > 0 ? windowEnd(before, now, askedAt, seconds) : 0
    const left = end.current - now
    if (left <= 0) {
      end.current = 0
      setShown(null)
      return undefined
    }
    if (before <= now) setShown({ id: now, seconds: left / 1000 })
    const timer = window.setTimeout(() => {
      end.current = 0
      setShown(null)
    }, left)
    return () => window.clearTimeout(timer)
  }, [askedAt, seconds])

  return shown
}
