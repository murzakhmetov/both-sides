/** The sections in the order of the page. The ids are also the anchors. */
export const SECTIONS = [
  'hero',
  'problem',
  'insight',
  'how',
  'verdict',
  'example',
  'deny',
  'demo',
  'why',
  'status',
  'closing',
] as const

export type SectionId = (typeof SECTIONS)[number]
