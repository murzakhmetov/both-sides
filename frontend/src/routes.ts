export type Screen = 'start' | 'receiver' | 'sender' | 'stage' | 'console' | 'demo' | 'login' | 'notfound'

const SCREENS: readonly Screen[] = ['start', 'receiver', 'sender', 'stage', 'console', 'demo', 'login']
const STAFF_PATH = /^\/(?:stage|demo|console(?:\/BS-\d{4}-\d{4,6})?)$/
const CASE_PATH = /^\/console\/(BS-\d{4}-\d{4,6})$/

export function screenOf(pathname: string): Screen {
  const first = pathname.split('/')[1] ?? ''
  return SCREENS.find((screen) => screen === first) ?? 'notfound'
}

export function caseIdOf(pathname: string): string | null {
  return CASE_PATH.exec(pathname)?.[1] ?? null
}

/** Only this app's own staff pages may follow a login. */
export function safeNext(search: string): string {
  const next = new URLSearchParams(search).get('next') ?? ''
  return STAFF_PATH.test(next) ? next : '/demo'
}

export function loginPath(next: string): string {
  return STAFF_PATH.test(next) ? `/login?next=${next}` : '/login'
}
