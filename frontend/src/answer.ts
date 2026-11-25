// The phone asks for "who" and "what for". An answer such as "my brother" names only one of them and goes
// to a person, so the phone asks once before it is sent. The server's own rules stay as they are.

/** Words that say neither who it is nor what the money is for. */
const EMPTY: ReadonlySet<string> = new Set(
  [
    'мой моя моё мое моего моей моему мою мои моим моими моих мне меня мной свой своя свои своему своей своего наш наша нашему нашей',
    'это эта этот эти был была было были деньги денег деньгами деньга тенге перевод перевода переводом сумма сумму',
    'перевел перевёл перевела перевели прислал прислала прислали отправил отправила отправили послал послала',
    'скинул скинула скинули кинул кинула кинули дал дала дали получил получила получили',
    'для просто спасибо привет пожалуйста ладно хорошо окей него неё нее ему',
    'менің маған менен өзім өзімнің бұл осы ақша ақшаны ақшасын ақшасы теңге аударым аударды аудардым',
    'жіберді жібердім жіберген жібердi салды салдым салған берді бердім берген алдым рахмет рақмет үшін сәлем',
    'the this that mine our his her him from for and was were money cash transfer transferred tenge',
    'sent send gave give got received thanks thank please okay hello just',
  ].flatMap((line) => line.split(' ')),
)

/** Somebody who writes that he knows nothing of it has said what there is to say. */
const DENIES: ReadonlySet<string> = new Set(
  'не нет никто никого ничего незнаю емес жоқ жок ешкім білмеймін танымаймын not nobody nothing dont unknown'.split(' '),
)

const SHORTEST = 3
const ENOUGH = 2

/** True for "Мой брат" or "аренда": one half of the question is still open. */
export function saysTooLittle(text: string): boolean {
  const words = text.toLowerCase().replace(/[’'`]/g, '').match(/\p{L}+/gu) ?? []
  if (words.some((word) => DENIES.has(word))) return false
  return words.filter((word) => word.length >= SHORTEST && !EMPTY.has(word)).length < ENOUGH
}
