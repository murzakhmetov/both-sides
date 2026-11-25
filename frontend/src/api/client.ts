// A small fetch wrapper around the common envelope {success, data | error}.

/** A request that hangs (Wi-Fi gone, laptop asleep) counts as offline after this time. */
const TIMEOUT_MS = 8000
/** A server that has just started takes a few seconds, and what a person did must not get lost. */
const ACTION_TIMEOUT_MS = 15_000
/** Online the reply to an answer waits for the comparison, and the language model may take 20 seconds. */
const ANSWER_TIMEOUT_MS = 28_000

export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(code: string, status: number) {
    super(code)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

interface Envelope {
  readonly success: boolean
  readonly data?: unknown
  readonly error?: string
}

function isEnvelope(value: unknown): value is Envelope {
  return typeof value === 'object' && value !== null && 'success' in value
}

async function readEnvelope(response: Response): Promise<Envelope> {
  try {
    const value: unknown = await response.json()
    if (isEnvelope(value)) return value
  } catch {
    // Not JSON: handled below like any other unexpected reply.
  }
  throw new ApiError('server_error', response.status)
}

function timeout(path: string, method: string | undefined): number {
  // The laptop answers at once and compares later, so there a long silence is a broken connection.
  if (method !== 'POST' || globalThis.location?.protocol !== 'https:') return TIMEOUT_MS
  return path.endsWith('/answer') ? ANSWER_TIMEOUT_MS : ACTION_TIMEOUT_MS
}

async function send<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      credentials: 'same-origin',
      cache: 'no-store',
      signal: AbortSignal.timeout(timeout(path, init.method)),
      ...init,
    })
  } catch {
    throw new ApiError('offline', 0)
  }
  const envelope = await readEnvelope(response)
  if (!envelope.success) throw new ApiError(envelope.error ?? 'server_error', response.status)
  return envelope.data as T
}

export function get<T>(path: string): Promise<T> {
  return send<T>(path, { method: 'GET' })
}

export function post<T>(path: string, body: Readonly<Record<string, string>> = {}): Promise<T> {
  return send<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function errorCode(error: unknown): string {
  return error instanceof ApiError ? error.code : 'server_error'
}
