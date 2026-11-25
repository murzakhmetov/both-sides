import type { TextKey } from './texts'

/** Typed answers and case numbers of the app's scenes (bothsides/demo/scenes.py). Answers are never translated. */

export interface Answer {
  readonly text: string
  readonly lang?: 'ru' | 'kk'
  readonly translation?: TextKey
}

/** Scene 1 of the app: the brother's rent. */
export const RENT = {
  receiver: { text: 'ағам пәтер жалдау ақысының жартысын жіберді', lang: 'kk', translation: 'how.answer.recipient' },
  sender: { text: 'Брату, моя половина аренды квартиры', lang: 'ru', translation: 'how.answer.sender' },
} as const satisfies Record<string, Answer>

/** Scene 2 of the app: the coached mother and the account owner. */
export const MOTHER = {
  receiver: { text: 'друг вернул долг', lang: 'ru', translation: 'example.recipient.translation' },
  sender: { text: 'сестре на лечение', lang: 'ru', translation: 'example.sender.translation' },
} as const satisfies Record<string, Answer>

export const CASE_NUMBERS = { mother: 'BS-2026-0002', stranger: 'BS-2026-0003' } as const

export interface Pair {
  readonly label: TextKey
  readonly receiver: Answer
  readonly sender: Answer
}

/** Filled in at the start. */
export const FIRST_PAIR: Pair = { label: 'demo.example.mother', ...MOTHER }

/** Pairs a visitor can try with one tap. */
export const PAIRS: readonly Pair[] = [
  FIRST_PAIR,
  { label: 'demo.example.rent', ...RENT },
  {
    label: 'demo.example.half',
    receiver: { text: 'половина аренды', lang: 'ru' },
    sender: { text: 'половина за лечение', lang: 'ru' },
  },
  { label: 'demo.example.nonsense', receiver: { text: 'asdf qwer' }, sender: { text: 'asdf qwer' } },
]
