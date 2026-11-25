import { expect, test, type FrameLocator, type Page } from '@playwright/test'

const PASSWORD = 'local-e2e-password'
const CONFIRM_HINT = 'Нажмите ещё раз в течение 4 секунд, чтобы подтвердить'

interface Demo {
  readonly receiver: FrameLocator
  readonly sender: FrameLocator
  readonly stage: FrameLocator
}

// Every test fails on a console error, which includes blocked scripts and styles.
test.beforeEach(({ page }) => {
  page.on('console', (message) => {
    if (message.type() === 'error') throw new Error(`console: ${message.text()}`)
  })
  page.on('pageerror', (error) => {
    throw error
  })
})

async function signIn(page: Page, path: string): Promise<void> {
  await page.goto(path)
  await page.locator('input[type=password]').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти' }).click()
  await page.waitForURL((url) => url.pathname === path)
}

async function openDemo(page: Page): Promise<Demo> {
  await page.setViewportSize({ width: 1366, height: 768 })
  await signIn(page, '/demo')
  return {
    receiver: page.frameLocator('iframe[src="/receiver"]'),
    sender: page.frameLocator('iframe[src="/sender"]'),
    stage: page.frameLocator('iframe[src="/stage?embed=1"]'),
  }
}

async function choose(page: Page, demo: Demo, name: RegExp): Promise<void> {
  const numbers = [demo.receiver, demo.sender].map((phone) => phone.locator('footer p').first())
  const before = await Promise.all(numbers.map((number) => number.innerText()))
  await page.getByRole('button', { name }).click()
  // Both phones show the new case at once, not after the next poll.
  for (const [index, number] of numbers.entries()) await expect(number).not.toHaveText(before[index] ?? '', { timeout: 700 })
  await expect(page.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true')
  await expect(demo.receiver.locator('textarea')).toHaveValue('')
}

async function answerBoth(page: Page, demo: Demo): Promise<void> {
  const fill = page.getByRole('button', { name: 'Вставить ответ сцены' })
  await fill.first().click()
  await demo.receiver.getByRole('button', { name: 'Отправить ответ' }).click()
  await expect(demo.sender.locator('textarea')).toBeVisible()
  await fill.last().click()
  await demo.sender.getByRole('button', { name: 'Отправить ответ' }).click()
}

test('scene 1: two languages, credited on both phones, also three times in a row', async ({ page }) => {
  const demo = await openDemo(page)
  for (let round = 0; round < 3; round += 1) {
    await choose(page, demo, /Аренда брата/)
    await answerBoth(page, demo)
    await expect(demo.receiver.getByRole('heading', { name: 'Зачислено' })).toBeVisible()
    await expect(demo.sender.getByRole('heading', { name: 'Зачислено' })).toBeVisible()
    await expect(demo.stage.getByText('Один и тот же перевод')).toBeVisible()
    await expect(demo.stage.getByText('ағам пәтер жалдау ақысының жартысын жіберді')).toBeVisible()
    await expect(demo.stage.getByText('Брату, моя половина аренды квартиры')).toBeVisible()
  }
})

test('scene 2: the sister story goes to a person, and the phones do not say why', async ({ page }) => {
  const demo = await openDemo(page)
  await choose(page, demo, /История про/)
  await answerBoth(page, demo)
  await expect(demo.receiver.getByRole('heading', { name: 'У специалиста' })).toBeVisible()
  await expect(demo.sender.getByRole('heading', { name: 'У специалиста' })).toBeVisible()
  await expect(demo.stage.getByText('Истории расходятся')).toBeVisible()
  for (const phone of [demo.receiver, demo.sender]) {
    await expect(phone.locator('body')).not.toContainText(/вероятность|расходятся|риск|сестре на лечение|друг вернул долг/)
  }
})

test('scene 3: two taps, return offer, good-faith notice with the case number', async ({ page }) => {
  const demo = await openDemo(page)
  await choose(page, demo, /Деньги незнакомца/)
  const deny = demo.receiver.getByRole('button', { name: 'Я не знаю этого человека' })
  await deny.click()
  await expect(demo.receiver.getByText(CONFIRM_HINT)).toBeVisible()
  await deny.click()
  await expect(demo.receiver.getByRole('heading', { name: 'Вы поступили добросовестно' })).toBeVisible()
  await expect(demo.receiver.getByText(/BS-\d{4}-\d{4}/).first()).toBeVisible()
  // The button takes no tap in its first moment, so that a third quick tap returns nothing.
  await page.waitForTimeout(900)
  await demo.receiver.getByRole('button', { name: 'Вернуть деньги' }).click()
  await expect(demo.receiver.getByRole('heading', { name: 'Возвращено' })).toBeVisible()
  await expect(demo.receiver.getByRole('heading', { name: 'Вы поступили добросовестно' })).toBeVisible()
  await expect(demo.sender.getByRole('heading', { name: 'Возвращено' })).toBeVisible()
})

test('one tap alone is not a denial', async ({ page }) => {
  const demo = await openDemo(page)
  await choose(page, demo, /Деньги незнакомца/)
  await demo.receiver.getByRole('button', { name: 'Я не знаю этого человека' }).click()
  await page.waitForTimeout(5200)
  await expect(demo.receiver.getByText(CONFIRM_HINT)).toBeHidden()
  await expect(demo.receiver.locator('textarea')).toBeVisible()
})

test('the specialist reads the case file and returns the money', async ({ page }) => {
  const demo = await openDemo(page)
  await choose(page, demo, /История про/)
  await answerBoth(page, demo)
  await expect(demo.sender.getByRole('heading', { name: 'У специалиста' })).toBeVisible()
  await page.goto('/console')
  const file = page.locator('article')
  await expect(file).toContainText('сестре на лечение')
  await expect(file).toContainText('друг вернул долг')
  await expect(file).toContainText('не более пяти рабочих дней')
  await expect(file).toContainText('risky_facts')
  await file.getByRole('button', { name: 'Вернуть' }).click()
  await page.waitForTimeout(600) // a confirmation right after the first click does not count
  await file.getByRole('button', { name: /Подтвердить: вернуть/ }).click()
  await expect(file.getByText('Обращение закрыто')).toBeVisible()
  await page.goto('/sender')
  await expect(page.getByRole('heading', { name: 'Возвращено' })).toBeVisible()
})

test('staff pages ask for the password and say when it is wrong', async ({ page }) => {
  await page.goto('/console')
  await expect(page).toHaveURL(/\/login\?next=\/console$/)
  page.removeAllListeners('console') // the browser reports the refused login itself
  await page.locator('input[type=password]').fill('not the password')
  await page.getByRole('button', { name: 'Войти' }).click()
  await expect(page.getByText('Неверный пароль.')).toBeVisible()
})

for (const path of ['/receiver', '/sender', '/start', '/login']) {
  test(`${path} fits a 360 px phone in three languages`, async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 740 })
    await page.goto(path)
    for (const [label, lang] of [['Русский', 'ru'], ['Қазақша (бета)', 'kk'], ['English', 'en']] as const) {
      const option = page.locator('header').getByRole('button', { name: lang === 'kk' ? /Қазақша/ : label })
      await option.click()
      await expect(option).toHaveAttribute('aria-pressed', 'true')
      const width = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(width).toBe(0)
      await expect(page.getByText(/ана тілінде сөйлейтін/)).toHaveCount(lang === 'kk' ? 1 : 0)
    }
    if (path === '/receiver' || path === '/sender') {
      const heights = await page.locator('button:visible').evaluateAll((all) => all.map((one) => one.getBoundingClientRect().height))
      expect(Math.min(...heights)).toBeGreaterThanOrEqual(48)
      const small = await page.locator('main, footer').evaluateAll((areas) =>
        areas
          .flatMap((area) => [...area.querySelectorAll('*')])
          .filter((one) => !one.closest('.sr-only') && [...one.childNodes].some((node) => node.nodeType === 3 && node.textContent?.trim()))
          .filter((one) => Number.parseFloat(getComputedStyle(one).fontSize) < 18)
          .map((one) => one.textContent),
      )
      expect(small).toEqual([])
    }
  })
}

test('dark mode follows the system and motion can be reduced', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto('/receiver')
  const light = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' })
  await page.reload()
  const dark = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
  expect(dark).not.toBe(light)
  const duration = await page.evaluate(() => {
    const dot = document.createElement('span')
    dot.className = 'animate-breathe'
    document.body.append(dot)
    return getComputedStyle(dot).animationDuration
  })
  expect(Number.parseFloat(duration)).toBeLessThan(0.01)
})
