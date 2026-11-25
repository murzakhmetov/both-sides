import type { CaseFile } from './api/types'
import type { Key } from './i18n'

export type Verdict = 'same' | 'differ' | 'unclear' | 'pending' | 'comparing' | 'not_compared'

/** The short words next to the match bar. The decision itself is made on the server. */
export function verdictOf(file: CaseFile): Verdict {
  const { match, thresholds } = file
  if (match === null) {
    if (file.state === 'comparing') return 'comparing'
    if (file.state === 'awaiting_receiver' || file.state === 'awaiting_sender') return 'pending'
    return 'not_compared'
  }
  if (match.probability >= thresholds.release && match.same_reason === 'true') return 'same'
  // A low score alone is not a contradiction: two empty or senseless answers are unclear.
  const apart = match.same_reason !== 'unknown' || match.same_relation === 'false'
  return match.probability < thresholds.hold && apart ? 'differ' : 'unclear'
}

export function verdictKey(verdict: Verdict): Key {
  return `verdict.${verdict}`
}

/** The status colours stay with their statuses: a credited case is green only when the stories are the same. */
export function barColor(file: CaseFile, verdict: Verdict): string {
  if (file.state === 'held') return 'bg-held'
  if (file.state === 'with_specialist') return 'bg-specialist-fill'
  return file.state === 'credited' && verdict === 'same' ? 'bg-credited' : 'bg-line-strong'
}
