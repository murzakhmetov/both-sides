/** The public comparison of the project server: the offline matcher and the content rule, nothing else. */

export const MAX_ANSWER_LENGTH = 300
export const MIN_ANSWER_LENGTH = 2
const TIMEOUT_MS = 10_000

export type TryResult = 'match' | 'specialist'
/** "refused": the server found nothing to compare in an answer; "long": an answer counts more than it looks. */
export type TryError = 'busy' | 'refused' | 'long' | 'server'

export interface TryAnswer {
  readonly result: TryResult
  /** Reason codes of the app; empty for a match. */
  readonly reasons: readonly string[]
}

export class TryFailed extends Error {
  readonly code: TryError

  constructor(code: TryError) {
    super(code)
    this.code = code
  }
}

function isTexts(value: unknown): value is readonly string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

/** Reads an answer of the server and trusts nothing in it. */
export function parseAnswer(body: unknown): TryAnswer {
  const data = (body as { data?: unknown } | null)?.data as Partial<Record<keyof TryAnswer, unknown>> | undefined
  const { result, reasons } = data ?? {}
  if ((result !== 'match' && result !== 'specialist') || !isTexts(reasons)) {
    throw new TryFailed('server')
  }
  return { result, reasons }
}

/** Why the server did not take the answers. */
async function refusal(response: Response): Promise<TryError> {
  const body = (await response.json().catch(() => null)) as { error?: unknown } | null
  return body?.error === 'too_long' ? 'long' : 'refused'
}

/** Compares two answers. Throws {@link TryFailed}. */
export async function compareAnswers(receiver: string, sender: string): Promise<TryAnswer> {
  let response: Response
  try {
    response = await fetch('/api/try', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ receiver, sender }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    })
  } catch {
    throw new TryFailed('server')
  }
  if (response.status === 429) throw new TryFailed('busy')
  if (response.status === 400) throw new TryFailed(await refusal(response))
  if (!response.ok) throw new TryFailed('server')
  try {
    return parseAnswer(await response.json())
  } catch (error) {
    throw error instanceof TryFailed ? error : new TryFailed('server')
  }
}
