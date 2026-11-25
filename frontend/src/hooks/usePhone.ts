import { useCallback, useEffect, useRef, useState } from 'react'
import { errorCode, post } from '../api/client'
import type { PhoneView, Side } from '../api/types'
import { useDenyWindow } from './useDenyWindow'
import { usePoll } from './usePoll'

const POLL_MS = 1000
export const FILL_MESSAGE = 'bothsides:fill'

export type PhoneAction = 'answer' | 'deny' | 'accept-return' | 'objection'

export interface FillMessage {
  readonly type: typeof FILL_MESSAGE
  readonly side: Side
  readonly caseId: string
  readonly text: string
}

export function isFillMessage(value: unknown): value is FillMessage {
  if (typeof value !== 'object' || value === null) return false
  const message = value as Partial<FillMessage>
  return message.type === FILL_MESSAGE && typeof message.text === 'string' && typeof message.caseId === 'string'
}

/** Puts the demo page's text into the field, also when it arrives before the new case does. */
function useFill(side: Side, caseId: string | null, setText: (text: string) => void): void {
  const [pending, setPending] = useState<FillMessage | null>(null)

  useEffect(() => {
    const listen = (event: MessageEvent<unknown>) => {
      if (event.origin !== window.location.origin || !isFillMessage(event.data)) return
      if (event.data.side === side) setPending(event.data)
    }
    window.addEventListener('message', listen)
    return () => window.removeEventListener('message', listen)
  }, [side])

  useEffect(() => {
    if (pending === null || pending.caseId !== caseId) return
    setText(pending.text)
    setPending(null)
  }, [caseId, pending, setText])
}

interface Failure {
  readonly code: string
  /** The screen on which the action was started. */
  readonly screen: string
}

function screenOf(view: PhoneView | null): string {
  return view ? `${view.case_id} ${view.status}` : ''
}

/** A lost reply must not leave its error on the screen that came next. */
export function shownError(failure: Failure | null, screen: string): string {
  if (failure === null) return ''
  return failure.screen === screen || failure.code === 'stale_case' ? failure.code : ''
}

/** One action at a time, but the two taps of a denial may follow each other at once. */
export function mayStart(action: PhoneAction, onWay: readonly PhoneAction[]): boolean {
  return onWay.every((other) => other === 'deny' && action === 'deny')
}

/** State and actions of one customer phone. */
export function usePhone(side: Side) {
  const poll = usePoll<PhoneView>(`/api/phone/${side}`, POLL_MS)
  const { data: view, apply, refresh } = poll
  const [text, setText] = useState('')
  const [running, setRunning] = useState<PhoneAction | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const onWay = useRef<readonly PhoneAction[]>([])
  const caseId = view?.case_id ?? null
  const screen = screenOf(view)
  const denial = useDenyWindow(view, poll.askedAt)

  // A new transfer starts with an empty field. This comes before useFill, which may
  // already have the text for the new transfer.
  useEffect(() => setText(''), [caseId])

  useFill(side, caseId, setText)

  const type = useCallback((value: string) => {
    setText(value)
    setFailure(null)
  }, [])

  const act = useCallback(
    async (action: PhoneAction, body: Readonly<Record<string, string>> = {}) => {
      if (caseId === null || !mayStart(action, onWay.current)) return
      onWay.current = [...onWay.current, action]
      setRunning(action)
      setFailure(null)
      try {
        await apply(() => post<PhoneView>(`/api/phone/${side}/${action}`, { case_id: caseId, ...body }))
        if (action === 'answer') setText('')
      } catch (error) {
        setFailure({ code: errorCode(error), screen })
        refresh()
      } finally {
        onWay.current = onWay.current.slice(1)
        if (onWay.current.length === 0) setRunning(null)
      }
    },
    [apply, caseId, refresh, screen, side],
  )

  const error = shownError(failure, screen)
  return { view, problem: poll.errorCode, text, type, running, error, act, denial }
}

export type Phone = ReturnType<typeof usePhone>
