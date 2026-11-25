import { useRef, useState, type FormEvent } from 'react'
import { MIN_ANSWER_LENGTH, TryFailed, compareAnswers, type TryAnswer, type TryError } from '../api'
import { FIRST_PAIR, type Answer, type Pair } from '../examples'
import type { TextKey } from '../texts'

/** A typed answer. Its language is known only when it was prepared. */
export type Draft = Pick<Answer, 'text' | 'lang'>

export type DemoState =
  | { readonly kind: 'idle' }
  | { readonly kind: 'busy' }
  | { readonly kind: 'done'; readonly answer: TryAnswer }
  | { readonly kind: 'error'; readonly text: TextKey }

const IDLE: DemoState = { kind: 'idle' }
const EMPTY: DemoState = { kind: 'error', text: 'demo.error.empty' }

const ERROR_TEXTS: Readonly<Record<TryError, TextKey>> = {
  busy: 'demo.error.busy',
  refused: 'demo.error.empty',
  long: 'demo.error.long',
  server: 'demo.error.server',
}

export function isEmpty(draft: Draft): boolean {
  return draft.text.trim().length < MIN_ANSWER_LENGTH
}

async function ask(receiver: Draft, sender: Draft): Promise<DemoState> {
  try {
    return { kind: 'done', answer: await compareAnswers(receiver.text, sender.text) }
  } catch (error) {
    return { kind: 'error', text: ERROR_TEXTS[error instanceof TryFailed ? error.code : 'server'] }
  }
}

/** What the visitor typed and what the server said about exactly that text. */
export function useDemo() {
  const [receiver, setReceiver] = useState<Draft>(FIRST_PAIR.receiver)
  const [sender, setSender] = useState<Draft>(FIRST_PAIR.sender)
  const [state, setState] = useState<DemoState>(IDLE)
  const request = useRef(0)

  /** An answer of the server that is still on its way belongs to the old text. */
  const forget = () => {
    request.current += 1
    setState(IDLE)
  }
  const change = (side: 'receiver' | 'sender', text: string) => {
    if (side === 'receiver') setReceiver({ text })
    else setSender({ text })
    forget()
  }
  const choose = (pair: Pair) => {
    setReceiver(pair.receiver)
    setSender(pair.sender)
    forget()
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (state.kind === 'busy') return
    if (isEmpty(receiver) || isEmpty(sender)) {
      setState(EMPTY)
      return
    }
    request.current += 1
    const mine = request.current
    setState({ kind: 'busy' })
    const next = await ask(receiver, sender)
    if (request.current === mine) setState(next)
  }
  return { receiver, sender, state, change, choose, submit }
}

export type Demo = ReturnType<typeof useDemo>
