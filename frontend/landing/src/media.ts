/** Every background of the page. Files: landing-media/, built by landing-media/build_media.py. */

export type Aspect = '16x9' | '9x16'

export type SceneId =
  | 'hero'
  | 'freeze'
  | 'whisper'
  | 'terraces'
  | 'chambers'
  | 'core'
  | 'return'
  | 'line'
  | 'monolith'
  | 'match'
  | 'mismatch'

export interface Scene {
  /** File name without the aspect. */
  readonly file: string
  /** A still has no video. A loop starts again, a clip stays on its last frame. */
  readonly kind: 'still' | 'loop' | 'clip'
}

export const SCENES: Readonly<Record<SceneId, Scene>> = {
  hero: { file: 'a-hero', kind: 'loop' },
  freeze: { file: 'b-freeze', kind: 'clip' },
  whisper: { file: 'c-whisper', kind: 'loop' },
  terraces: { file: 'bg-terraces', kind: 'still' },
  chambers: { file: 'd-chambers', kind: 'clip' },
  core: { file: 'e-core', kind: 'loop' },
  match: { file: 'f-match', kind: 'clip' },
  mismatch: { file: 'g-mismatch', kind: 'clip' },
  return: { file: 'h-return', kind: 'clip' },
  line: { file: 'bg-line', kind: 'still' },
  monolith: { file: 'bg-monolith', kind: 'still' },
}

const BASE = '/assets/landing'

/** Set by the build (vite.config.ts); tests run without it. */
declare const __MEDIA_VERSION__: string | undefined
const VERSION = typeof __MEDIA_VERSION__ === 'string' ? `?v=${__MEDIA_VERSION__}` : ''

/** The first frame, or the last frame of a clip. */
export function posterUrl(id: SceneId, aspect: Aspect, ended = false): string {
  return `${BASE}/${SCENES[id].file}-${aspect}${ended ? '-end' : ''}.webp${VERSION}`
}

/** WebM first: it is always the smaller file (the tests check that). MP4 for browsers without it. */
export function videoSources(id: SceneId, aspect: Aspect): readonly { readonly src: string; readonly type: string }[] {
  if (SCENES[id].kind === 'still') return []
  const name = `${BASE}/${SCENES[id].file}-${aspect}`
  return [
    { src: `${name}.webm${VERSION}`, type: 'video/webm' },
    { src: `${name}.mp4${VERSION}`, type: 'video/mp4' },
  ]
}

/** Scenes that come right before or after a scene on the page: they are loaded early, the rest later. */
const NEIGHBOURS: Readonly<Record<SceneId, readonly SceneId[]>> = {
  hero: ['freeze', 'line'],
  freeze: ['hero', 'whisper'],
  whisper: ['freeze', 'terraces'],
  terraces: ['whisper', 'chambers', 'core', 'return'],
  chambers: ['terraces', 'core'],
  core: ['chambers', 'terraces'],
  return: ['terraces', 'line'],
  line: ['return', 'monolith', 'hero'],
  monolith: ['line'],
  // Both play inside their own section, which loads them itself.
  match: [],
  mismatch: [],
}

/** The backgrounds behind the page. */
export const BACKDROPS = (Object.keys(SCENES) as SceneId[]).filter((id) => NEIGHBOURS[id].length > 0)

export function isNear(id: SceneId, active: SceneId): boolean {
  return id === active || NEIGHBOURS[active].includes(id)
}
