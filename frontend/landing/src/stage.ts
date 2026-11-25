import type { SceneId } from './media'

/** A background, and whether its clip waits on the first frame. */
export interface Shown {
  readonly scene: SceneId
  readonly held: boolean
}

interface Claim extends Shown {
  readonly section: string
}

/** Every section on screen claims its background; the last claim that still stands is shown. */
export interface Stage {
  readonly claims: readonly Claim[]
  readonly shown: Shown
}

export const START: Stage = { claims: [], shown: { scene: 'hero', held: false } }

function others(stage: Stage, section: string): readonly Claim[] {
  return stage.claims.filter((claim) => claim.section !== section)
}

export function claim(stage: Stage, section: string, shown: Shown): Stage {
  return { claims: [...others(stage, section), { ...shown, section }], shown }
}

/** Between two sections the last background stays. */
export function release(stage: Stage, section: string): Stage {
  const claims = others(stage, section)
  const last = claims.at(-1)
  return { claims, shown: last ? { scene: last.scene, held: last.held } : stage.shown }
}
