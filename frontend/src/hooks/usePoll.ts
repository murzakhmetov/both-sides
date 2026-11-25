import { useCallback, useEffect, useRef, useState } from 'react'
import { errorCode as codeOf, get } from '../api/client'

/** The demo page sends this to its frames after a scene change, so nobody waits for the next poll. */
export const REFRESH_MESSAGE = 'bothsides:refresh'

/** Keeps replies in the order in which their requests were sent. */
export class ReplyOrder {
  private sent = 0
  private applied = 0

  /** Call when a request goes out. */
  next(): number {
    this.sent += 1
    return this.sent
  }

  /** True when no reply of a later request is already on the screen. */
  accept(order: number): boolean {
    if (order < this.applied) return false
    this.applied = order
    return true
  }

  /**
   * The same for the reply to an action. Polls that are still under way were sent before this
   * reply came, so another copy of the server may answer them with the state before the action.
   */
  acceptAction(order: number): boolean {
    if (!this.accept(order)) return false
    this.applied = this.sent + 1
    return true
  }
}

export interface Poll<T> {
  readonly data: T | null
  /** When the request behind the data was sent, on the clock of performance.now(). */
  readonly askedAt: number
  /** Code of the last failed request, empty after a good one. */
  readonly errorCode: string
  readonly refresh: () => void
  /** Runs another request whose reply is the same kind of data. */
  readonly apply: (request: () => Promise<T>) => Promise<void>
}

interface Reply<T> {
  readonly data: T
  readonly askedAt: number
}

/** Asks the server again and again, never two polls at once. */
export function usePoll<T>(path: string | null, intervalMs: number): Poll<T> {
  const [reply, setReply] = useState<Reply<T> | null>(null)
  const [errorCode, setErrorCode] = useState('')
  const order = useRef(new ReplyOrder())
  const currentPath = useRef<string | null>(null)
  const wake = useRef<() => void>(() => undefined)

  useEffect(() => {
    currentPath.current = path
    if (path === null) return undefined
    let stopped = false
    let timer: number | undefined
    let running = false
    let askAgain = false

    const ask = async () => {
      if (stopped) return
      if (running) {
        askAgain = true
        return
      }
      running = true
      askAgain = false
      window.clearTimeout(timer)
      const number = order.current.next()
      const askedAt = performance.now()
      try {
        const next = await get<T>(path)
        if (stopped) return
        if (order.current.accept(number)) setReply({ data: next, askedAt })
        setErrorCode('')
      } catch (error) {
        if (!stopped) setErrorCode(codeOf(error))
      } finally {
        running = false
        // A tab that nobody sees asks nothing; it asks at once when it is shown again.
        if (!stopped && !document.hidden) timer = window.setTimeout(() => void ask(), askAgain ? 0 : intervalMs)
      }
    }

    const listen = (event: MessageEvent<unknown>) => {
      if (event.origin === window.location.origin && event.data === REFRESH_MESSAGE) void ask()
    }
    const wakeUp = () => {
      if (document.visibilityState === 'visible') void ask()
    }
    wake.current = () => void ask()
    window.addEventListener('message', listen)
    window.addEventListener('online', wakeUp)
    document.addEventListener('visibilitychange', wakeUp)
    void ask()
    return () => {
      stopped = true
      window.removeEventListener('message', listen)
      window.removeEventListener('online', wakeUp)
      document.removeEventListener('visibilitychange', wakeUp)
      window.clearTimeout(timer)
    }
  }, [path, intervalMs])

  const refresh = useCallback(() => wake.current(), [])
  const apply = useCallback(
    async (request: () => Promise<T>) => {
      const number = order.current.next()
      const askedAt = performance.now()
      const next = await request()
      // The user may have moved on to another case while the request ran.
      if (currentPath.current !== path) return
      if (order.current.acceptAction(number)) setReply({ data: next, askedAt })
      else wake.current()
    },
    [path],
  )

  return { data: reply?.data ?? null, askedAt: reply?.askedAt ?? 0, errorCode, refresh, apply }
}
