// The phone asks for "who" and "what for". An answer such as "my brother" names only one of them and goes
// to a person, so the phone asks once before it is sent. The server's own rules stay as they are: this only
// looks for the missing half, with the app's own list of relations and reasons.

import lexicon from '../../bothsides/data/lexicon.json'

type Entry = string | readonly string[] | { readonly phrase: readonly string[] }
type Concepts = Readonly<Record<string, { readonly entries: readonly Entry[] }>>

const PLAIN: Readonly<Record<string, string>> = {
  ә: 'а', ғ: 'г', қ: 'к', ң: 'н', ө: 'о', ұ: 'у', ү: 'у', һ: 'х', і: 'и', ё: 'е',
}

function fold(text: string): string {
  return text.toLowerCase().replace(/[әғқңөұүһіё]/g, (letter) => PLAIN[letter] ?? letter)
}

function folded(...lines: readonly string[]): ReadonlySet<string> {
  return new Set(lines.flatMap((line) => fold(line).split(' ')))
}

/** Words that say neither who it is nor what the money is for. */
const EMPTY = folded(
  'мой моя моё моего моей моему мою мои моим моими моих меня мной мне свой своя свои своему своей своего наш наша нашему нашей',
  'это эта этот эти этому этой был была было были его ему него неё ней нему она они оно там тут все всё просто тоже уже ещё опять',
  'деньги денег деньгами деньга денежку денюжку денежка тенге перевод перевода переводом сумма сумму карта карту каспи',
  'перевел перевела перевели переводил переводила перечислил перечислила переслал переслала прислал прислала прислали присылал',
  'отправил отправила отправили отправлял отправляла послал послала скинул скинула скинули скидывал скидывала кинул кинула кинули кидал',
  'закинул закинула дал дала дали отдал отдала получил получила вернул вернула вернули возврат возвращает',
  'старший старшая старшему старшей младший младшая младшему младшей родной родная родному двоюродный двоюродная двоюродному',
  'лучший лучшая лучшему близкий близкая хороший хорошая хорошему старый давний один одна какой',
  'для спасибо привет пожалуйста ладно хорошо окей как чтобы',
  'менің маған менен өзім өзімнің бұл осы ақша ақшаны ақшасын ақшасы теңге аударым аударды аудардым аударған',
  'жіберді жібердім жіберген жібердi салды салдым салған берді бердім берген алдым қайтарды қайтардым рахмет рақмет үшін сәлем деп',
  'үлкен кіші туған жақын жақсы ескі ақы ақысы ақысын ақысына төлем төлемі тастады лақтырды ғой ғана',
  'день дня рождения рождение күн күні күнге күніне',
  'the this that mine our his her him from for and was were money cash transfer transferred tenge card',
  'sent send gave give got received paid pay returned repayment repaid thanks thank please okay hello just',
  'older elder younger best good old close big little thats hes shes its',
)

/** Two letters that are no word of their own. Others may be: "др", "зп", "кв", "үй", "ем", "tv". */
const PARTICLES = folded(
  'на за от до из по со во ко об ни но да же ли бы то он мы вы ты их им её ей не ну ой ай эй так де ма ба па пе ме бе ол ал',
  'to of in on at my me is it he we us so or an as by be do go up if ok hi no',
)

/** Somebody who writes that this is a mistake or a stranger has said what there is to say. */
const DENIES = folded(
  'не нет неа нету никто никого никому ничего незнаю хз емес жоқ ешкім случайно кто что кім қате',
  'no not never nobody nothing none nope dont didnt wasnt isnt cant doesnt unknown idk dunno wrong error who what',
)
const DENIAL_STEMS = [...folded('ошиб неизвест незнаком мошен чуж посторон забыл бейтаныс бөтен таныма білме білми қателік қателес stranger mistake scam')]

interface WordList {
  readonly words: ReadonlySet<string>
  /** A stem, and the endings that it may have (null: any short one). */
  readonly stems: readonly (readonly [string, ReadonlySet<string> | null])[]
  readonly phrases: readonly (readonly string[])[]
}

const ENDINGS = lexicon.endings as Readonly<Record<string, readonly string[]>>

function wordList(concepts: Concepts): WordList {
  const entries = Object.values(concepts).flatMap((concept) => concept.entries)
  return {
    words: new Set(entries.filter((entry) => typeof entry === 'string').map(fold)),
    stems: entries
      .filter((entry): entry is readonly string[] => Array.isArray(entry))
      .map(([stem = '', kind = '']) => [fold(stem), ENDINGS[kind] ? new Set(ENDINGS[kind]) : null] as const),
    phrases: entries.flatMap((entry) => (typeof entry === 'object' && 'phrase' in entry ? [entry.phrase.map(fold)] : [])),
  }
}

const RELATIONS = wordList(lexicon.relations as Concepts)
const REASONS = wordList(lexicon.reasons as Concepts)

function names(list: WordList, word: string): boolean {
  if (list.words.has(word)) return true
  return list.stems.some(([stem, endings]) => {
    if (!word.startsWith(stem)) return false
    const tail = word.slice(stem.length)
    return endings ? endings.has(tail) : tail.length <= lexicon.any_max_tail
  })
}

function phraseIn(list: WordList, words: readonly string[]): boolean {
  const fits = (pattern: string, word: string | undefined) =>
    word !== undefined && (pattern.endsWith('*') ? word.startsWith(pattern.slice(0, -1)) : word === pattern)
  return list.phrases.some((phrase) => words.some((_, start) => phrase.every((pattern, index) => fits(pattern, words[start + index]))))
}

/** True for "Мой брат" or "за аренду квартиры": one half of the question is still open. */
export function saysTooLittle(text: string): boolean {
  const plain = fold(text).replace(/[’'`]/g, '').replace(/(\p{L})\/(\p{L})/gu, '$1$2')
  const words = plain.match(/\p{L}+/gu) ?? []
  if (words.some((word) => DENIES.has(word) || DENIAL_STEMS.some((stem) => word.startsWith(stem)))) return false
  const who = words.some((word) => names(RELATIONS, word)) || phraseIn(RELATIONS, words)
  const why = words.some((word) => names(REASONS, word)) || phraseIn(REASONS, words)
  if (who && why) return false
  // A name, or a reason that the list does not know, may be the other half.
  const others = words.filter(
    (word) => word.length > 1 && !EMPTY.has(word) && !PARTICLES.has(word) && !names(RELATIONS, word) && !names(REASONS, word),
  )
  return others.length < (who || why ? 1 : 2)
}
