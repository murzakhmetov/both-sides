import { expect, test, type Page } from '@playwright/test'

// Every test fails on a console error, which includes blocked scripts, styles and videos.
test.beforeEach(({ page }) => {
  page.on('console', (message) => {
    if (message.type() === 'error') throw new Error(`console: ${message.text()}`)
  })
  page.on('pageerror', (error) => {
    throw error
  })
})

/** Scrolls to a section; 0 is its top, 1 its end. */
async function scrollTo(page: Page, id: string, part = 0): Promise<void> {
  await page.evaluate(
    ([name, share]) => {
      const box = document.getElementById(name)?.getBoundingClientRect()
      if (!box) throw new Error(`no section ${name}`)
      window.scrollTo(0, box.top + window.scrollY + Math.max(0, box.height - window.innerHeight) * share)
    },
    [id, part] as const,
  )
}

function playing(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll('video')]
      .filter((video) => !video.paused && !video.ended)
      .map((video) => new URL(video.currentSrc).pathname.split('/').pop() ?? ''),
  )
}

async function compare(page: Page, receiver: string, sender: string): Promise<void> {
  await page.getByLabel('Recipient says…').fill(receiver)
  await page.getByLabel('Sender says…').fill(sender)
  await page.getByRole('button', { name: 'Compare' }).click()
}

test('the first page says what it is, in three languages, and remembers the choice', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle('Both sides · Hackathon project for the BCC case')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('We ask both sides.')
  await expect(page.locator('footer')).toContainText('Not an official BCC website.')
  await page.getByRole('button', { name: 'KZ Қазақша' }).click()
  await expect(page.locator('html')).toHaveAttribute('lang', 'kk')
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Біз екі тараптан да сұраймыз.')
  await page.getByRole('button', { name: 'RU Русский' }).click()
  await expect(page.locator('footer')).toContainText('Не официальный сайт BCC.')
})

test('the live demo opens from the landing page', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Open the live demo' }).first().click()
  await expect(page).toHaveURL(/\/start$/)
})

test('the mini-demo gives the verdict of the offline matcher', async ({ page }) => {
  await page.goto('/')
  await scrollTo(page, 'demo')
  const specialist = page.locator('#demo').getByText('With a specialist', { exact: true })
  // The mother story is filled in.
  await page.getByRole('button', { name: 'Compare' }).click()
  await expect(specialist).toBeVisible()
  await expect(page.getByText('No shared reason')).toBeVisible()

  await page.getByRole('button', { name: 'Brother’s rent' }).click()
  await expect(specialist).toBeHidden()
  await page.getByRole('button', { name: 'Compare' }).click()
  await expect(page.getByText('MATCH', { exact: true })).toBeVisible()

  for (const [receiver, sender] of [
    ['половина аренды', 'половина за лечение'],
    ['asdf qwer', 'asdf qwer'],
    ['я не знаю этого человека', 'брату на аренду квартиры'],
  ] as const) {
    await compare(page, receiver, sender)
    await expect(specialist).toBeVisible()
  }
})

test('the mini-demo asks for a missing answer and can be used with the keyboard', async ({ page }) => {
  await page.goto('/')
  await scrollTo(page, 'demo')
  const sender = page.getByLabel('Sender says…')
  await page.getByLabel('Recipient says…').fill('друг вернул долг')
  await sender.fill(' ')
  await sender.press('Tab')
  await expect(page.getByRole('button', { name: 'Compare' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByText('Please write both answers, at least 2 characters each.')).toBeVisible()
  await expect(sender).toHaveAttribute('aria-invalid', 'true')
  await sender.fill('сестре на лечение')
  await expect(sender).toHaveAttribute('aria-invalid', 'false')
})

test('"I do not know this person" needs two taps and shows the notice', async ({ page }) => {
  await page.goto('/')
  await scrollTo(page, 'deny', 0.3)
  await page.getByRole('button', { name: 'I do not know this person' }).click()
  await expect(page.getByText('You acted in good faith').last()).toBeHidden()
  await page.getByRole('button', { name: /Tap again/ }).click()
  await expect(page.getByText('You acted in good faith').last()).toBeVisible()
  await expect(page.locator('#deny')).toContainText('Example case, invented data')
})

test('the keyboard reaches everything from the top of the page, without scrolling first', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/')
  const wanted = ['Open the live demo', 'Article on bcc.kz', 'I do not know this person', 'The mother story', 'Compare']
  const reached: string[] = []
  for (let step = 0; step < 45; step += 1) {
    await page.keyboard.press('Tab')
    const text = await page.evaluate(() => document.activeElement?.textContent ?? '')
    for (const name of wanted) if (text.includes(name) && !reached.includes(name)) reached.push(name)
  }
  expect(reached).toEqual(wanted)
})

test('the returned money can be shown again from the start', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/')
  await scrollTo(page, 'deny', 0.3)
  const button = page.locator('#deny button')
  const time = () => page.evaluate(() => document.querySelector<HTMLVideoElement>('[data-scene=return] video')?.currentTime ?? -1)
  await button.click()
  await button.click()
  await expect.poll(time).toBeGreaterThan(1)
  await button.click()
  await expect.poll(time).toBe(0)
  await expect.poll(() => playing(page)).toEqual([])
  await button.click()
  await button.click()
  await expect.poll(() => playing(page)).toEqual(['h-return-16x9.webm'])
})

test('one video plays at a time, and the button stops it', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/')
  await expect.poll(() => playing(page)).toEqual(['a-hero-16x9.webm'])
  await scrollTo(page, 'verdict', 0.2)
  await expect.poll(() => playing(page)).toEqual(['f-match-16x9.webm'])
  await scrollTo(page, 'verdict', 0.85)
  await expect.poll(() => playing(page)).toEqual(['g-mismatch-16x9.webm'])
  await page.getByRole('button', { name: 'Stop the moving background' }).click()
  await expect.poll(() => playing(page)).toEqual([])
  await scrollTo(page, 'hero')
  await page.waitForTimeout(600)
  expect(await playing(page)).toEqual([])
})

test('a video is loaded only when its scene is on', async ({ page }) => {
  const videos: string[] = []
  page.on('request', (request) => {
    const name = new URL(request.url()).pathname.split('/').pop() ?? ''
    if (/\.(?:mp4|webm)$/.test(name) && !videos.includes(name)) videos.push(name)
  })
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/')
  await expect.poll(() => playing(page)).toEqual(['a-hero-16x9.webm'])
  expect(videos).toEqual(['a-hero-16x9.webm'])
  await scrollTo(page, 'insight', 0.5)
  await page.waitForTimeout(1500)
  expect(videos.filter((name) => !/^(?:a-hero|b-freeze|c-whisper)/.test(name))).toEqual([])
})

test('a phone gets the upright files and nothing is wider than the window', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 })
  await page.goto('/')
  await expect(page.locator('#hero').getByText('Hackathon project for the BCC case')).toBeVisible()
  await expect.poll(() => playing(page)).toEqual(['a-hero-9x16.webm'])
  for (const name of ['EN English', 'RU Русский', 'KZ Қазақша']) {
    await page.getByRole('button', { name }).click()
    const wider = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(wider, name).toBeLessThanOrEqual(0)
  }
})

test('the background follows when the reader turns around', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 810 })
  await page.goto('/')
  const scene = () => page.evaluate(() => document.querySelector('.backdrop .media-layer[data-active=true]')?.getAttribute('data-scene'))
  for (const [before, after, first, second] of [
    ['problem', 'insight', 'whisper', 'terraces'],
    ['demo', 'why', 'line', 'monolith'],
    ['why', 'status', 'monolith', 'line'],
  ] as const) {
    const border = await page.evaluate((id) => (document.getElementById(id)?.getBoundingClientRect().top ?? 0) + window.scrollY - window.innerHeight / 2, after)
    for (const [offset, wanted] of [[-200, first], [30, second], [-30, first], [30, second]] as const) {
      await page.evaluate((y) => window.scrollTo(0, y), border + offset)
      await expect.poll(scene, { message: `${before}/${after} ${offset}` }).toBe(wanted)
    }
  }
})

test('a link to a section opens with the background of that section', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 810 })
  const scene = () => page.evaluate(() => document.querySelector('.backdrop .media-layer[data-active=true]')?.getAttribute('data-scene'))
  for (const [id, wanted] of [['demo', 'line'], ['why', 'monolith'], ['demo', 'line'], ['problem', 'whisper'], ['demo', 'line'], ['deny', 'return'], ['demo', 'line']] as const) {
    await page.goto('about:blank')
    await page.goto(`/#${id}`)
    await page.waitForTimeout(1000)
    expect(await scene(), id).toBe(wanted)
  }
})

test('a reload keeps the place', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 810 })
  await page.goto('/')
  for (let round = 0; round < 5; round += 1) {
    await scrollTo(page, 'verdict', 0.4)
    await page.waitForTimeout(500)
    const before = await page.evaluate(() => window.scrollY)
    await page.reload()
    await page.waitForTimeout(700)
    expect(Math.abs((await page.evaluate(() => window.scrollY)) - before), `round ${round}`).toBeLessThan(40)
  }
})

test('the phones never touch the words of their step', async ({ page }) => {
  test.setTimeout(60_000)
  const windows = [[1440, 764], [1366, 641], [1280, 593], [390, 844], [360, 560]] as const
  for (const [width, height] of windows) {
    await page.setViewportSize({ width, height })
    await page.goto('/')
    for (const name of ['EN English', 'RU Русский']) {
      await page.getByRole('button', { name }).click()
      for (const step of [1, 3]) {
        await scrollTo(page, 'how', (step + 0.5) / 6)
        await page.waitForTimeout(700)
        const over = await page.evaluate(() => {
          const words = document.querySelector('.how-steps .caption')?.getBoundingClientRect().top ?? 0
          const phones = [...document.querySelectorAll('.how-phone')].filter((item) => getComputedStyle(item).opacity !== '0')
          return Math.max(...phones.map((item) => (item.querySelector('.phone-mock')?.getBoundingClientRect().bottom ?? 0) - words))
        })
        expect(over, `${width}x${height} ${name} step ${step + 1}`).toBeLessThanOrEqual(1)
      }
    }
  }
})

test('less motion: no video is loaded and the clips show how they end', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1366, height: 768 } })
  const page = await context.newPage()
  const videos: string[] = []
  page.on('request', (request) => {
    if (/\.(?:mp4|webm)(?:\?|$)/.test(request.url())) videos.push(request.url())
  })
  await page.goto('/')
  for (const [id, part] of [['hero', 0.9], ['how', 0.2], ['verdict', 0.2], ['deny', 0.3]] as const) {
    await scrollTo(page, id, part)
    await page.waitForTimeout(200)
  }
  expect(videos).toEqual([])
  await expect(page.locator('video')).toHaveCount(0)
  await scrollTo(page, 'verdict', 0.2)
  await expect(page.locator('.verdict-panel img').first()).toHaveAttribute('src', /f-match-16x9-end\.webp/)
  await context.close()
})
