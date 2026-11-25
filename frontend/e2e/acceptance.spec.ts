// Gaps that an acceptance check against the brief confirmed. Every test failed before its fix.
import { expect, test, type Browser, type Page } from '@playwright/test'

const PASSWORD = 'local-e2e-password'
const LANGUAGES = [/Русский/, /Қазақша/, /English/]

// Windows that stay open keep asking the server, and after enough tests that is one request too many.
test.afterEach(async ({ browser, context }) => {
  await Promise.all(browser.contexts().filter((other) => other !== context).map((other) => other.close()))
})

async function signIn(page: Page, path: string): Promise<void> {
  await page.goto(path)
  await page.locator('input[type=password]').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти' }).click()
  await page.waitForURL((url) => url.pathname === path)
}

async function post(page: Page, path: string): Promise<void> {
  const status = await page.evaluate(async (target) => {
    const init = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }
    return (await fetch(target, init)).status
  }, path)
  expect(status, path).toBe(200)
}

async function activeCase(page: Page): Promise<string> {
  return page.evaluate(async () => (await (await fetch('/api/cases')).json()).data.active_id as string)
}

async function newPhone(browser: Browser): Promise<Page> {
  return (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage()
}

async function answerBoth(browser: Browser, receiver: string, sender: string): Promise<void> {
  const phone = await newPhone(browser)
  for (const [side, text] of [['receiver', receiver], ['sender', sender]] as const) {
    await phone.goto(`/${side}`)
    await phone.locator('textarea').fill(text)
    await phone.getByRole('button', { name: 'Отправить ответ' }).click()
    await expect(phone.locator('textarea')).toBeHidden()
  }
}

async function overflow(page: Page): Promise<number> {
  await page.waitForTimeout(250)
  return page.evaluate(() => document.documentElement.scrollHeight - document.documentElement.clientHeight)
}

test('a tap on the hint presses nothing behind it', async ({ browser, page }) => {
  await signIn(page, '/stage')
  await post(page, '/api/scenes/stranger/start')
  const phone = await newPhone(browser)
  await phone.goto('/receiver')
  await phone.locator('textarea').fill('друг вернул долг')
  const deny = phone.getByRole('button', { name: 'Я не знаю этого человека' })
  await deny.click()
  const hint = phone.locator('#deny-hint')
  await expect(hint).toContainText('Нажмите ещё раз')
  const box = (await hint.boundingBox()) ?? { x: 0, y: 0, width: 0, height: 0 }
  await phone.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
  await expect(phone.locator('textarea')).toHaveValue('друг вернул долг')
  await deny.click()
  await expect(phone.getByRole('heading', { name: 'Мы можем вернуть эти деньги' })).toBeVisible()
})

test('two quick taps are a denial also on a slow network', async ({ browser, page }) => {
  await signIn(page, '/stage')
  await post(page, '/api/scenes/stranger/start')
  const phone = await newPhone(browser)
  await phone.route('**/api/phone/receiver/deny', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 600))
    await route.continue()
  })
  await phone.goto('/receiver')
  const deny = phone.getByRole('button', { name: 'Я не знаю этого человека' })
  await deny.click()
  await phone.waitForTimeout(200)
  await deny.click()
  await expect(phone.getByRole('heading', { name: 'Мы можем вернуть эти деньги' })).toBeVisible()
  await expect(phone.locator('[role=alert]')).toHaveCount(0)
})

test('a third quick tap does not press the button that has just appeared', async ({ browser, page }) => {
  await signIn(page, '/stage')
  for (const [width, height] of [[360, 640], [375, 553], [375, 667], [390, 844]] as const) {
    await post(page, '/api/scenes/stranger/start')
    const phone = await newPhone(browser)
    await phone.setViewportSize({ width, height })
    await phone.goto('/receiver')
    const deny = phone.getByRole('button', { name: 'Я не знаю этого человека' })
    await deny.scrollIntoViewIfNeeded()
    const box = (await deny.boundingBox()) ?? { x: 0, y: 0, width: 0, height: 0 }
    for (let tap = 0; tap < 3; tap += 1) {
      await phone.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
      await phone.waitForTimeout(250)
    }
    const offer = phone.getByRole('button', { name: 'Вернуть деньги' })
    await expect(offer, `${width}x${height}`).toBeVisible()
    await phone.waitForTimeout(900)
    await offer.click()
    await expect(phone.getByRole('heading', { name: 'Возвращено' })).toBeVisible()
  }
})

test('the same nonsense on both phones is unclear, not two different stories', async ({ browser, page }) => {
  await signIn(page, '/stage')
  for (const text of ['asdf qwer', 'спасибо большое', 'бәрі жақсы рахмет']) {
    await post(page, '/api/scenes/brother/start')
    await answerBoth(browser, text, text)
    await expect(page.getByText('Неясно', { exact: true })).toBeVisible()
    await expect(page.getByText('Истории расходятся')).toBeHidden()
  }
})

test('the stage still fits after a person decided', async ({ browser, page }) => {
  test.setTimeout(60_000)
  await signIn(page, '/stage')
  await post(page, '/api/reset')
  // The same story at two other receivers adds a fourth reason.
  for (const scene of ['brother', 'stranger']) {
    await post(page, `/api/scenes/${scene}/start`)
    await answerBoth(browser, 'друг вернул долг', 'сестре на лечение')
  }
  for (const [receiver, sender] of [['друг вернул долг', 'сестре на лечение'], ['спасибо большое', 'спасибо большое']] as const) {
    await post(page, '/api/scenes/sister/start')
    await answerBoth(browser, receiver, sender)
    await post(page, `/api/cases/${await activeCase(page)}/release`)
    await expect(page.getByText('Зачислено').first()).toBeVisible()
    for (const [width, height] of [[1366, 768], [1536, 730], [1920, 937], [1920, 1080]] as const) {
      await page.setViewportSize({ width, height })
      for (const name of LANGUAGES) {
        await page.getByRole('button', { name }).click()
        expect(await overflow(page), `${width}x${height} ${name} ${receiver}`).toBeLessThanOrEqual(0)
      }
    }
    await page.getByRole('button', { name: /Русский/ }).click()
  }
})

test('the middle of the demo page fits after a person decided', async ({ browser, page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await signIn(page, '/demo')
  await post(page, '/api/scenes/sister/start')
  await answerBoth(browser, 'друг вернул долг', 'сестре на лечение')
  await post(page, `/api/cases/${await activeCase(page)}/release`)
  const stage = page.frames().find((frame) => frame.url().includes('embed=1'))
  for (const name of LANGUAGES) {
    await page.getByRole('button', { name }).first().click()
    await page.waitForTimeout(400)
    const over = await stage?.evaluate(() => document.documentElement.scrollHeight - document.documentElement.clientHeight)
    expect(over, String(name)).toBeLessThanOrEqual(0)
  }
})

test('a reset while a case is open in the console shows no error', async ({ page }) => {
  await signIn(page, '/console')
  await expect(page.getByRole('listitem').first()).toBeVisible()
  await page.evaluate(() => {
    new MutationObserver(() => {
      if (document.body.innerText.includes('Ничего не найдено')) document.body.dataset['seen'] = 'error'
    }).observe(document.body, { childList: true, subtree: true, characterData: true })
  })
  for (let round = 0; round < 3; round += 1) {
    await post(page, '/api/reset')
    await page.waitForTimeout(2200)
  }
  expect(await page.evaluate(() => document.body.dataset['seen'] ?? '')).toBe('')
})

test('the console names the risky facts and fades a new status in', async ({ browser, page }) => {
  await signIn(page, '/console')
  await post(page, '/api/scenes/sister/start')
  await answerBoth(browser, 'друг вернул долг', 'сестре на лечение')
  const row = page.getByRole('listitem').filter({ hasText: 'Гульнар → Тимур' }).first()
  await expect(row).toContainText('new_account, many_first_time_senders, no_earlier_transfers')
  await expect(row).toContainText('У специалиста')
  await page.evaluate(() => {
    document.addEventListener('animationstart', (event) => {
      document.body.dataset['seen'] = `${document.body.dataset['seen'] ?? ''} ${event.animationName}`
    })
  })
  await post(page, `/api/cases/${await activeCase(page)}/release`)
  await expect(row).toContainText('Зачислено')
  await expect.poll(() => page.evaluate(() => document.body.dataset['seen'] ?? '')).toContain('enter')
})
