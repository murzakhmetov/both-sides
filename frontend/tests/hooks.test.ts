import { describe, expect, it } from 'vitest'
import { windowEnd } from '../src/hooks/useDenyWindow'
import { FILL_MESSAGE, isFillMessage, mayStart, shownError } from '../src/hooks/usePhone'
import { ReplyOrder } from '../src/hooks/usePoll'

describe('order of replies', () => {
  it('takes replies that arrive in order', () => {
    const order = new ReplyOrder()
    const first = order.next()
    const second = order.next()
    expect(order.accept(first)).toBe(true)
    expect(order.accept(second)).toBe(true)
  })

  it('leaves out a reply that is older than the one on the screen', () => {
    const order = new ReplyOrder()
    const slowPost = order.next()
    const poll = order.next()
    expect(order.accept(poll)).toBe(true)
    expect(order.accept(slowPost)).toBe(false)
    expect(order.accept(order.next())).toBe(true)
  })
})

describe('the window for the second tap', () => {
  it('is counted from when the request was sent, not from when the reply came', () => {
    expect(windowEnd(0, 1800, 1000, 4)).toBe(5000)
  })

  it('is never made longer by a later reply', () => {
    expect(windowEnd(5000, 2000, 1500, 3.9)).toBe(5000)
    expect(windowEnd(5000, 2000, 1500, 3.1)).toBe(4600)
  })

  it('starts again after it has closed', () => {
    expect(windowEnd(5000, 6000, 6000, 4)).toBe(10000)
  })
})

describe('actions on their way', () => {
  it('run one at a time', () => {
    expect(mayStart('answer', [])).toBe(true)
    expect(mayStart('answer', ['answer'])).toBe(false)
    expect(mayStart('answer', ['deny'])).toBe(false)
    expect(mayStart('deny', ['answer'])).toBe(false)
  })

  it('let the second tap of a denial follow the first at once', () => {
    expect(mayStart('deny', ['deny'])).toBe(true)
  })
})

describe('errors of an action', () => {
  it('stay on the screen on which the action was started', () => {
    const failure = { code: 'offline', screen: 'BS-1 question' }
    expect(shownError(failure, 'BS-1 question')).toBe('offline')
    expect(shownError(failure, 'BS-1 return_offer')).toBe('')
    expect(shownError(null, 'BS-1 question')).toBe('')
  })

  it('explain on the next screen why an answer was too late', () => {
    expect(shownError({ code: 'stale_case', screen: 'BS-1 question' }, 'BS-2 question')).toBe('stale_case')
  })
})

describe('messages of the demo page', () => {
  it('need a case, so that the text of one scene never lands in another', () => {
    expect(isFillMessage({ type: FILL_MESSAGE, side: 'sender', caseId: 'BS-2026-1234', text: 'text' })).toBe(true)
    expect(isFillMessage({ type: FILL_MESSAGE, side: 'sender', text: 'text' })).toBe(false)
  })

  it.each([null, 'text', 7, {}, { type: 'other', caseId: 'x', text: 'y' }, { type: FILL_MESSAGE, caseId: 1, text: 'y' }])(
    'ignore %j',
    (value) => {
      expect(isFillMessage(value)).toBe(false)
    },
  )
})

describe('the reply to an action', () => {
  it('makes polls that were under way useless', () => {
    const order = new ReplyOrder()
    const action = order.next()
    const poll = order.next()
    expect(order.acceptAction(action)).toBe(true)
    expect(order.accept(poll)).toBe(false)
    expect(order.accept(order.next())).toBe(true)
  })

  it('gives way to a later poll that is already on the screen', () => {
    const order = new ReplyOrder()
    const action = order.next()
    expect(order.accept(order.next())).toBe(true)
    expect(order.acceptAction(action)).toBe(false)
    expect(order.accept(order.next())).toBe(true)
  })

  it('lets two actions follow each other', () => {
    const order = new ReplyOrder()
    const first = order.next()
    const second = order.next()
    expect(order.acceptAction(first)).toBe(true)
    expect(order.acceptAction(second)).toBe(false)
    expect(order.accept(order.next())).toBe(true)
  })
})
