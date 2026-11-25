import { describe, expect, it } from 'vitest'
import { statesOf } from '../src/components/Tracker'

describe('transfer tracker', () => {
  it.each([
    [{ status: 'waiting', answered: false }, ['done', 'now', 'later']],
    [{ status: 'waiting', answered: true }, ['done', 'done', 'now']],
    [{ status: 'with_specialist', answered: true }, ['done', 'done', 'now']],
    // Nobody answers for this person any more, so the step is not shown as the next one.
    [{ status: 'with_specialist', answered: false }, ['done', 'later', 'now']],
  ] as const)('case %#', (view, states) => {
    expect(statesOf(view)).toEqual(states)
  })
})
