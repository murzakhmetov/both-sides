import { describe, expect, it } from 'vitest'
import { caseIdOf, loginPath, safeNext, screenOf } from '../src/routes'

describe('login target', () => {
  it.each(['/demo', '/stage', '/console', '/console/BS-2026-0007'])('keeps the staff page %s', (path) => {
    expect(safeNext(`?next=${path}`)).toBe(path)
    expect(loginPath(path)).toBe(`/login?next=${path}`)
  })

  it.each([
    'https://evil.example/demo',
    '//evil.example',
    '/\\evil.example',
    'javascript:alert(1)',
    '/demo/../../evil',
    '/receiver',
    '/console/BS-2026-0007/x',
    '',
  ])('never follows %s', (path) => {
    expect(safeNext(`?next=${encodeURIComponent(path)}`)).toBe('/demo')
    expect(loginPath(path)).toBe('/login')
  })
})

describe('screens', () => {
  it('reads the screen from the path', () => {
    expect(screenOf('/receiver')).toBe('receiver')
    expect(screenOf('/console/BS-2026-0007')).toBe('console')
    expect(screenOf('/nothing')).toBe('notfound')
    expect(screenOf('/')).toBe('notfound')
  })

  it('reads the case number from the path', () => {
    expect(caseIdOf('/console/BS-2026-0007')).toBe('BS-2026-0007')
    expect(caseIdOf('/console')).toBeNull()
  })
})
