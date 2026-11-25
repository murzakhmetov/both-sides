import { describe, expect, it } from 'vitest'
import { saysTooLittle } from '../src/answer'

describe('an answer with only one half', () => {
  it.each([
    'Мой брат', 'моя сестра', 'брат', 'Брат отправил', 'брат прислал деньги', 'аренда', 'за аренду', 'подарок', 'мне скинул друг',
    'ок', 'спасибо', 'брату 5000', 'ағам', 'ағам жіберді', 'менің анам', 'my brother', 'my sister sent money', 'rent', '   ', '🙂',
  ])('asks for the other half: %s', (text) => {
    expect(saysTooLittle(text)).toBe(true)
  })

  it.each([
    'брат отправил за аренду квартиры', 'сестре за аренду квартиры', 'друг вернул долг', 'сестре на лечение', 'Брату, моя половина аренды квартиры',
    'ағам пәтер жалдау ақысының жартысын жіберді', 'маме на лекарства', 'сестре подарок', 'анама дәріге', 'my brother, rent', 'mother for medicine',
    'сын за учёбу', 'половина ответа', 'asdf qwer',
  ])('lets a whole answer pass: %s', (text) => {
    expect(saysTooLittle(text)).toBe(false)
  })

  it.each([
    'не знаю', 'не знаю этого человека', 'никто', 'это не мне', 'білмеймін', 'танымаймын', 'бұл мен емес', "I don't know", 'nobody I know', 'нет',
  ])('does not press somebody who knows nothing of it: %s', (text) => {
    expect(saysTooLittle(text)).toBe(false)
  })
})
