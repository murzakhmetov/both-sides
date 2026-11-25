# Part 2: the landing page, its pictures and where everything is

The first plan (storm clouds) was dropped on 25 November 2026. The user's words: "use background like this in stile of bcc bank, forgot about that old", with a picture of matte graphite terraces, a gold sign and ribbed glass. This file describes what was built instead.

## 1. Look

- Matte graphite terraces, brushed gold, clear ribbed glass, low studio light.
- The gold object is the project's own mark: a disc cut into two halves. The bank's sign is not in any picture. The bank's logo is nowhere on the page.
- Gold stands for money and a match, BCC Green for the system and the AI. Muted red appears only where the stories do not match.
- The paper bills are an invented design with ram-horn ornament, not a copy of a real note.
- No faces, no words in the pictures. The page says that the videos and pictures were made with AI.

Colours, from the bank's brand guidebook (PDF, pages 16 and 17): BCC Green `#00B975`, BCC Gold `#DCA262`, with the light variants `#61D894`, `#F2BD7C` and `#FBE1BA` from the pages after them. They are variables in [landing.css](../frontend/landing/src/styles/landing.css). Source: <https://www.bcc.kz/static/bcc-kz-storage/storage/app/media/About%20the%20bank/brand/Centercredit_Brand_Assets.pdf>

Fonts: Geologica (headlines) and Onest (text), SIL Open Font License, bundled, with the Kazakh letters.

## 2. Where each picture is used

Every clip exists as MP4 and WebM in 16:9 and 9:16, with a poster (WebP). Clips that do not loop also have their last frame, for people who ask for less motion.

| Shot | File | Where | Plays |
|---|---|---|---|
| A | `a-hero` | Start, closing | loop |
| B | `b-freeze` | Start, after scrolling: "The transfer is stopped." | once |
| C | `c-whisper` | The problem | loop |
| still | `bg-terraces` | The insight, the example | |
| D | `d-chambers` | How it works, steps 1 to 3 | once |
| E | `e-core` | How it works, steps 4 to 6 | loop |
| F | `f-match` | The verdict, left half | once |
| G | `g-mismatch` | The verdict, right half | once |
| H | `h-return` | "I do not know this person", after two taps | once |
| still | `bg-line` | Mini-demo, honest status | |
| still | `bg-monolith` | Why BCC | |

Files: `landing-media/public/assets/landing/`. The build copies them to `web/assets/landing/`. [manifest.json](../landing-media/manifest.json) lists size, length, SHA-256 and the original take of every file; [plan.json](../landing-media/plan.json) holds the cuts.

Made with Google Flow: stills with Nano Banana Pro and Nano Banana 2.1 (0 credits), clips with Veo 3.1 Fast (20 credits each, 8 seconds, 720p). 21 clips were generated for 16 deliverables: 420 credits. Flow showed 615 credits afterwards.

The addresses of the files carry a version from the manifest, so a browser never shows an old clip after `npm run build`.

To build the files again from the originals (they are in `flow-mcp-out` in the home folder):

```bash
pip install imageio-ffmpeg
python landing-media/build_media.py --force
```

## 3. Prompts of the clips on the page

Every clip starts from an approved still, so the still fixes the place and the objects and the prompt describes the motion. The 9:16 clips use the same words plus "tall vertical picture".

**A. Hero (loop; first frame = last frame).** The three ornamental paper bills hover in the still studio air around the gold two-half disc: over the eight seconds each bill slowly rises a little, tilts a few degrees and sinks back to exactly where it began, like leaves resting on calm water. One soft studio light glides slowly across the scene from left to right and back, so a warm highlight travels over the brushed champagne gold, the fine flutes of the ribbed glass sparkle softly and thin grey highlights move along the rounded edges of the graphite terraces. The gold disc, the glass collar and the terraces stay perfectly still. Locked-off static camera, 50mm lens, one continuous shot. Matte graphite-black studio landscape, minimal premium 3D product visual, calm, dark, restrained. The motion ends exactly where it started so the clip loops seamlessly.

**B. The freeze.** A slow, quiet shot. 0.0-2.5 s: the three ornamental paper bills sway gently on the air around the gold two-half disc, each rising a little and sinking back to its place. 2.5-3.5 s: they slow down smoothly and come to rest. 3.5-8.0 s: all three bills hang perfectly motionless in mid-air, as if time had stopped for them, while one soft, dim band of studio light keeps gliding slowly across the gold disc, the ribbed glass and the edges of the terraces on the right side. The gold disc, the ribbed glass collar and the graphite terraces stay perfectly still. Locked-off static camera, 50mm lens, one continuous shot. Matte graphite-black studio landscape, the left half dark and calm, minimal premium 3D product visual, restrained.

**C. The whisper (loop).** The three thin ribbons of pale translucent light flow slowly and steadily from the front of the faceless graphite head through the air toward the phone and wind around it, like whispered breath, always in the same direction; the even cold glow of the phone brightens and dims a little once. The graphite bust, the phone, the ribbed glass plinth and the terraces stay perfectly still. Locked-off static camera, 50mm lens, one continuous shot. Dark matte graphite studio landscape, cold dim light, the left half dark and calm, ominous, abstract, minimal premium 3D product visual, restrained. The motion ends exactly where it started so the clip loops seamlessly.

**D. Two chambers.** 0.0-2.0 s: two phones glow calmly, each alone inside its own chamber of ribbed glass, on the left and on the right of the graphite wall. 2.0-6.0 s: from the foot of each glass chamber one thin straight line of pale green-white light grows along the groove in the graphite floor toward the wall in the centre, both at the same slow speed. 6.0-8.0 s: both lines touch the foot of the wall at the same moment and the vertical line of white light on the wall brightens softly. The phones, the glass chambers and the wall stay perfectly still. Very slow push-in on the centre axis, symmetrical wide shot, eye level, 50mm lens, one continuous shot. Matte graphite-black studio landscape, low even light, minimal premium 3D product visual, calm, dark, restrained.

**E. The core (loop).** Inside the still sphere of ribbed glass the round core made of fine jade-green points of light turns slowly around its vertical axis, always in the same direction at the same slow speed, its points twinkling softly. Along the two straight lines of light in the floor small soft pulses travel slowly inward, one from the left edge and one from the right edge, and vanish into the plinth. The glass sphere, the plinth and the graphite terraces stay perfectly still. Locked-off static camera, symmetrical wide shot, 50mm lens, one continuous shot. Matte graphite-black studio landscape, low even light, minimal premium 3D product visual, calm, dark, restrained. The motion ends exactly where it started so the clip loops seamlessly.

**F. Match (first frame apart, last frame joined).** 0.0-5.0 s: the two gold half-discs, standing in their ribbed glass holders, slide slowly and smoothly toward each other over the graphite floor. 5.0-6.0 s: their straight sides meet exactly in the centre and become one complete round disc; the green line of light between them becomes one hair-thin vertical seam of warm gold light. 6.0-8.0 s: a soft, calm gold glow grows gently from the seam and lies on the floor in front of the disc. During the whole shot the four ornamental paper bills stay at their places in the air and only sway very slightly, keeping their shape and their engraved pattern, their foil edges catching the light. Locked-off static camera, symmetrical wide shot, eye level, 50mm lens, one continuous shot. Matte graphite-black studio landscape, low even light, minimal premium 3D product visual, warm, relieving, restrained.

**G. Mismatch (same first frame as F).** A slow, quiet, restrained shot. 0.0-4.0 s: the two gold half-discs, standing upright in their ribbed glass holders, slide slowly toward each other over the graphite floor and stop: they do not fit and a clear gap stays between them. During these four seconds the four ornamental paper bills stay at their places in the air and only sway very slightly. 4.0-5.0 s: the green line of light between the halves dims and fades into two short faint pieces, one thin horizontal thread of muted, desaturated dark red light appears weakly across the gap, and the halves turn a few degrees away from each other. 5.0-8.0 s: the four bills sink slowly straight down from their places and settle on the graphite floor, keeping their shape and their engraved pattern, while the room light grows a little colder and dimmer. Locked-off static camera, symmetrical wide shot, eye level, 50mm lens, one continuous shot. Matte graphite-black studio landscape, low even light, minimal premium 3D product visual.

**H. Return.** The four ornamental paper bills that rest low above the terraces lift gently together and rise slowly and evenly straight up, side by side, calm and safe, like leaves carried upward by warm air, until they leave the picture through the top edge in the last second. Each bill keeps its size, its shape, its engraved pattern and its gentle bend and tilts only a few degrees. The terraces stay perfectly still. Locked-off static camera, 50mm lens, one continuous shot. Matte graphite-black studio landscape, warm soft light from above on the right, the left half dark and calm, minimal premium 3D product visual, gentle, restrained.

The sound of the clips is cut off: the page is silent.

Takes that were thrown away: F, first take (extra bills, one looked like a real note); G, two takes (too violent); B, first take (the bills changed shape); A, second take (the first is calmer).

## 4. Sections and code

| # | Section | File in `frontend/landing/src` |
|---|---|---|
| 0 | Nav: name, dots, languages, pause button, "Open the live demo" | `components/Nav.tsx` |
| 1 | Start: "We ask both sides.", then "The transfer is stopped." | `sections/Hero.tsx` |
| 2, 3 | The problem, the insight | `sections/Story.tsx` |
| 4 | How it works: six steps, two phones, the lock | `sections/How.tsx`, `components/PhoneMock.tsx` |
| 5 | The verdict: two halves, the case file slides out | `sections/Verdict.tsx` |
| 6 | The example: two puzzle pieces that do not fit | `sections/Example.tsx` |
| 7 | "I do not know this person" | `sections/Deny.tsx` |
| 8 | Mini-demo: `POST /api/try` | `sections/MiniDemo.tsx`, `components/DemoForm.tsx` |
| 9, 10, 11 | Why BCC, honest status, closing and footer | `sections/Proof.tsx` |

All words are in one object, `texts.ts`, in three languages; the typed example answers are in `examples.ts`, because they are never translated, and `index.html` holds the English title and description for the moment before the script runs. Status words, questions and reasons come from the app's own files, so both pages always say the same. The numbers in "Honest status" are read from `evaluation/results/offline.json` at build time: run `npm run build` again after an evaluation.

## 5. To replace or decide

| What | Where |
|---|---|
| Native check of the Russian and Kazakh texts | `texts.ts`, [kazakh-texts-for-review.md](kazakh-texts-for-review.md) |
| "Gemini version: not yet measured" and "Next: live model check" | `status.gemini`, `status.next`, after the live check has run |

## 6. Facts checked for the words

- The BCC article opened on 24 and 25 November 2026. It says that the victim is told to confirm the transfer and to say that the money goes to "маме, папе, брату или подруге". The Russian text keeps these words; the brief has "a friend".
- Article 25-1 of the Law on Payments is the same article that the app quotes on its screens.
- Only the numbers in "Honest status" come from the evaluation. 90 000 ₸ is the invented amount of scene 1 of the app, and the two case numbers are invented too; the age of the account (four days) and the five new senders come from the brief; five working days come from the law.
