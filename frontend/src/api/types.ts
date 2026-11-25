// Shapes of the JSON the Python server sends. Keep in step with bothsides/cases/views.py.

export type Side = 'receiver' | 'sender'
export type Tri = 'true' | 'false' | 'unknown'
export type FinalStatus = 'credited' | 'with_specialist' | 'held' | 'returned'
export type PhoneStatus = 'question' | 'waiting' | 'return_offer' | FinalStatus
export type CaseState = 'awaiting_receiver' | 'awaiting_sender' | 'comparing' | FinalStatus

export interface Names {
  readonly ru: string
  readonly kk: string
  readonly en: string
}

export interface PhoneView {
  readonly case_id: string
  readonly case_number: string
  readonly side: Side
  readonly status: PhoneStatus
  readonly answered: boolean
  readonly other_name: Names
  readonly amount: number
  readonly answer_by: string | null
  readonly deadline_at: string | null
  readonly ground: string
  readonly objection_sent: boolean
  readonly deny_armed_seconds?: number
  readonly message?: string | null
  /** Only on the receiver's own phone: this receiver said that the sender is unknown. */
  readonly denied?: boolean
}

export interface MatchView {
  readonly probability: number
  readonly same_relation: Tri
  readonly same_reason: Tri
  readonly note: string
  readonly source: 'gemini' | 'offline'
  readonly model: string
  readonly fallback_code: string
}

export interface FactsView {
  readonly account_age_days: number
  readonly first_time_senders_today: number
  readonly earlier_transfers: number
  readonly risky: readonly string[]
}

export interface CaseSummary {
  readonly id: string
  readonly scene: string | null
  readonly state: CaseState
  readonly reasons: readonly string[]
  readonly risky: readonly string[]
  readonly amount: number
  readonly sender: Names
  readonly receiver: Names
  readonly stopped_at: string
  readonly deadline_at: string
  readonly overdue: boolean
  readonly denied: boolean
  readonly objections: readonly Side[]
}

export interface AnswerView {
  readonly text: string
  readonly at: string
}

export interface TrailEntry {
  readonly at: string
  readonly actor: 'system' | 'receiver' | 'sender' | 'staff'
  readonly event: string
  readonly details: readonly string[]
}

/** The numbers of bothsides/config.py. */
export interface Thresholds {
  readonly release: number
  readonly hold: number
  readonly repeated_story: number
}

export interface CaseFile extends Omit<CaseSummary, 'objections'> {
  readonly thresholds: Thresholds
  readonly transfer: {
    readonly amount: number
    readonly message: string
    readonly sender: Names
    readonly receiver: Names
  }
  readonly facts: FactsView
  readonly match: MatchView | null
  readonly similar_receivers: number
  readonly receiver_answer: AnswerView | null
  readonly sender_answer: AnswerView | null
  readonly answer_by: string
  readonly decided_at: string | null
  readonly closed_at: string | null
  readonly seconds: number | null
  readonly objections: readonly { readonly side: Side; readonly at: string }[]
  readonly trail: readonly TrailEntry[]
}

export interface StageView {
  readonly scene: string | null
  readonly case: CaseFile
  readonly phones: Readonly<Record<Side, PhoneStatus>>
  readonly seconds: number | null
  readonly running_seconds: number | null
}

export interface CaseList {
  readonly active_id: string
  readonly cases: readonly CaseSummary[]
}

export interface Scene {
  readonly id: string
  readonly receiver_script: string
  readonly sender_script: string
}

export interface SceneList {
  readonly active: string | null
  readonly case_id: string
  readonly scenes: readonly Scene[]
}

export interface StatusView {
  readonly matcher: {
    readonly active: 'gemini' | 'offline'
    readonly reason: string
    readonly model: string
    readonly model_state: string
  }
  /** Online: the board belongs to this browser, and staff pages are open. */
  readonly sandbox: boolean
}
