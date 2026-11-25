import { existsSync, readFileSync, statSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TryFailed, compareAnswers, parseAnswer } from '../landing/src/api'
import { MOTHER, PAIRS, RENT } from '../landing/src/examples'
import { reasonText } from '../landing/src/lang'
import { BACKDROPS, SCENES, isNear, posterUrl, videoSources, type Aspect, type SceneId } from '../landing/src/media'
import { SECTIONS } from '../landing/src/sections'
import { START, claim, release } from '../landing/src/stage'
import { LANGS, TEXTS, fill, type TextKey } from '../landing/src/texts'

const ROOT = resolve(import.meta.dirname, '../..')
const KEYS = Object.keys(TEXTS.en) as TextKey[]
const IDS = Object.keys(SCENES) as SceneId[]
const ASPECTS: readonly Aspect[] = ['16x9', '9x16']

/** Where the build takes a media file from. */
function mediaFile(url: string): string {
  return resolve(ROOT, `landing-media/public${url}`)
}

function placeholders(text: string): string[] {
  return [...text.matchAll(/\{(\w+)\}/g)].map((found) => found[1] ?? '').sort()
}

describe('landing texts', () => {
  it.each(LANGS)('%s has every text and the same placeholders', (lang) => {
    expect(Object.keys(TEXTS[lang])).toEqual(KEYS)
    for (const key of KEYS) {
      expect(TEXTS[lang][key].trim(), key).not.toBe('')
      expect(placeholders(TEXTS[lang][key]), key).toEqual(placeholders(TEXTS.en[key]))
    }
  })

  it('says on every language that this is a hackathon project and not a BCC website', () => {
    for (const lang of LANGS) {
      expect(TEXTS[lang]['meta.title']).toContain('BCC')
      expect(TEXTS[lang]['nav.tag']).toContain('BCC')
      expect(TEXTS[lang]['footer.note']).toContain('ITU HACKATHON-2026')
    }
    expect(TEXTS.en['footer.note']).toBe('Hackathon project for the BCC case of ITU HACKATHON-2026. Not an official BCC website.')
  })

  it('keeps the honest status word for word', () => {
    expect(TEXTS.en['status.ai']).toBe('AI comparison: tested on simulated people only')
    expect(TEXTS.en['status.gemini']).toBe('Gemini version: not yet measured')
    expect(TEXTS.en['status.demo']).toBe('Demo: offline word list')
    expect(TEXTS.en['status.next']).toBe('Next: live model check')
    expect(TEXTS.en['demo.label']).toBe('Demo: offline word list. The language-model check runs in the full app.')
  })

  it('uses no hype words', () => {
    const all = LANGS.flatMap((lang) => Object.values(TEXTS[lang])).join(' ')
    expect(all).not.toMatch(/revolution|game-chang|cutting-edge|world-class|революц|прорыв|уникальн|инновацион/i)
  })

  it('has a name for every section', () => {
    for (const id of SECTIONS) expect(KEYS).toContain(`section.${id}`)
  })

  it('fills in values and leaves unknown placeholders', () => {
    expect(fill('{n} of {total}', { n: 2 })).toBe('2 of {total}')
  })
})

describe('landing media', () => {
  it('shows everything behind the page except the two clips of the split screen', () => {
    expect([...BACKDROPS, 'match', 'mismatch'].sort()).toEqual([...IDS].sort())
  })

  it('loads only the neighbours on the page early', () => {
    expect(isNear('hero', 'hero')).toBe(true)
    expect(isNear('freeze', 'hero')).toBe(true)
    expect(isNear('return', 'terraces')).toBe(true)
    expect(isNear('whisper', 'hero')).toBe(false)
    expect(isNear('match', 'terraces')).toBe(false)
  })

  it.each(ASPECTS)('has every file in %s, also the last frame of every clip', (aspect) => {
    for (const id of IDS) {
      const urls = [
        posterUrl(id, aspect),
        ...(SCENES[id].kind === 'clip' ? [posterUrl(id, aspect, true)] : []),
        ...videoSources(id, aspect).map((source) => source.src),
      ]
      for (const url of urls) expect(existsSync(mediaFile(url)), url).toBe(true)
    }
  })

  it.each(ASPECTS)('offers the smaller file first in %s', (aspect) => {
    for (const id of IDS) {
      const [first, second] = videoSources(id, aspect).map((source) => statSync(mediaFile(source.src)).size)
      if (first !== undefined && second !== undefined) expect(first, id).toBeLessThan(second)
    }
  })

  it('offers WebM first and no video for a still', () => {
    expect(videoSources('hero', '9x16').map((source) => source.src)).toEqual([
      '/assets/landing/a-hero-9x16.webm',
      '/assets/landing/a-hero-9x16.mp4',
    ])
    expect(videoSources('terraces', '16x9')).toEqual([])
    expect(posterUrl('monolith', '16x9')).toBe('/assets/landing/bg-monolith-16x9.webp')
    expect(posterUrl('match', '9x16', true)).toBe('/assets/landing/f-match-9x16-end.webp')
  })
})

describe('landing backgrounds', () => {
  const hero = { scene: 'hero', held: false } as const
  const line = { scene: 'line', held: false } as const

  it('shows the background of the section on screen, whatever event comes first', () => {
    const orders = [
      release(claim(claim(START, 'start', hero), 'demo', line), 'start'),
      claim(release(claim(START, 'start', hero), 'start'), 'demo', line),
      // The start section reports late that it was on screen, and then that it is gone.
      release(claim(claim(START, 'demo', line), 'start', hero), 'start'),
    ]
    for (const stage of orders) expect(stage.shown).toEqual(line)
  })

  it('keeps the last background between two sections and follows a section that changes its own', () => {
    const gone = release(claim(START, 'demo', line), 'demo')
    expect(gone).toEqual({ claims: [], shown: line })
    const waiting = claim(START, 'deny', { scene: 'return', held: true })
    expect(claim(release(waiting, 'deny'), 'deny', { scene: 'return', held: false }).shown).toEqual({ scene: 'return', held: false })
  })
})

describe('landing examples', () => {
  it('shows the answers of the scenes of the app, word for word', () => {
    const scenes = readFileSync(resolve(ROOT, 'bothsides/demo/scenes.py'), 'utf8')
    for (const pair of [RENT, MOTHER]) {
      expect(scenes).toContain(`receiver_script="${pair.receiver.text}"`)
      expect(scenes).toContain(`sender_script="${pair.sender.text}"`)
    }
  })

  it('starts with the mother story and offers the pair about two halves', () => {
    expect(PAIRS[0]).toMatchObject(MOTHER)
    const texts = PAIRS.map((pair) => [pair.receiver.text, pair.sender.text])
    expect(texts).toContainEqual(['половина аренды', 'половина за лечение'])
  })
})

describe('mini-demo', () => {
  afterEach(() => vi.unstubAllGlobals())

  const answer = (status: number, body: unknown) =>
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status })))

  it('reads a verdict of the server', async () => {
    answer(200, { success: true, data: { result: 'specialist', reasons: ['low_match', 'no_shared_reason'] } })
    expect(await compareAnswers('друг вернул долг', 'сестре на лечение')).toEqual({
      result: 'specialist',
      reasons: ['low_match', 'no_shared_reason'],
    })
  })

  it.each(LANGS)('knows the words for every reason of the server in %s, and no others', (lang) => {
    const source = readFileSync(resolve(ROOT, 'bothsides/decision/reasons.py'), 'utf8')
    const codes = [...source.matchAll(/^ {4}[A-Z_]+ = "([a-z_]+)"/gm)].map((found) => found[1] ?? '')
    expect(codes.length).toBeGreaterThanOrEqual(12)
    for (const code of codes) expect(reasonText(lang, code), code).toBeTruthy()
    for (const strange of ['not_a_reason', '__proto__', '']) expect(reasonText(lang, strange)).toBeNull()
  })

  it.each([
    [429, 'busy'],
    [400, 'refused'],
    [500, 'server'],
    [403, 'server'],
  ])('turns status %i into "%s"', async (status, code) => {
    answer(status, { success: false, error: 'x' })
    await expect(compareAnswers('a', 'b')).rejects.toMatchObject({ code })
  })

  it('knows an answer that is too long from one that is empty', async () => {
    answer(400, { success: false, error: 'too_long' })
    await expect(compareAnswers('a', 'b')).rejects.toMatchObject({ code: 'long' })
    answer(400, { success: false, error: 'empty_answer' })
    await expect(compareAnswers('a', 'b')).rejects.toMatchObject({ code: 'refused' })
  })

  it('reports a server that does not answer', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('network'))))
    await expect(compareAnswers('a', 'b')).rejects.toMatchObject({ code: 'server' })
  })

  it.each([
    null,
    {},
    { data: null },
    { data: { result: 'released', reasons: [] } },
    { data: { result: 'match', reasons: 'none' } },
    { data: { result: 'match', reasons: [1] } },
  ])('never trusts a strange body: %j', (body) => {
    expect(() => parseAnswer(body)).toThrow(TryFailed)
  })
})
