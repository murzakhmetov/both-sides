// What an independent review of the interface found. Every test failed before its fix.
import { expect, test, type Page } from '@playwright/test'

const PASSWORD = 'local-e2e-password'
const HELD = {
  case_id: 'BS-2026-1234',
  case_number: 'BS-2026-1234',
  side: 'receiver',
  status: 'held',
  answered: true,
  other_name: { ru: 'Гульнар', kk: 'Гүлнар', en: 'Gulnar' },
  amount: 450000,
  answer_by: null,
  deadline_at: '2026-12-02T18:00:00.000+05:00',
  ground: '25-1',
  objection_sent: false,
  deny_armed_seconds: 0,
  message: null,
  denied: false,
}

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

async function startScene(page: Page, scene: string): Promise<void> {
  const reply = await page.evaluate(async (id) => {
    const init = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }
    return (await fetch(`/api/scenes/${id}/start`, init)).status
  }, scene)
  expect(reply).toBe(200)
}

async function showPhone(page: Page, view: Readonly<Record<string, unknown>>): Promise<void> {
  await page.route('**/api/phone/receiver', (route) => route.fulfill({ json: { success: true, data: view } }))
}

test('a failed objection and a failed return say so', async ({ page }) => {
  await showPhone(page, HELD)
  await page.route('**/api/phone/receiver/objection', (route) =>
    route.fulfill({ status: 429, json: { success: false, error: 'rate_limited' } }),
  )
  await page.goto('/receiver')
  await page.getByRole('button', { name: 'Возразить' }).click()
  await expect(page.getByText('Слишком много запросов')).toBeVisible()

  await page.unroute('**/api/phone/receiver')
  await showPhone(page, { ...HELD, status: 'return_offer', denied: true })
  await page.route('**/api/phone/receiver/accept-return', (route) =>
    route.fulfill({ status: 500, json: { success: false, error: 'server_error' } }),
  )
  await page.goto('/receiver')
  await page.waitForTimeout(900)
  await page.getByRole('button', { name: 'Вернуть деньги' }).click()
  await expect(page.getByText('Что-то пошло не так')).toBeVisible()
})

test('an answer that comes too late for its transfer is explained', async ({ browser, page }) => {
  const staff = await (await browser.newContext()).newPage()
  await signIn(staff, '/demo')
  await startScene(staff, 'brother')
  await page.goto('/receiver')
  const number = page.locator('footer p').first()
  const before = await number.innerText()
  await page.locator('textarea').fill('брат прислал за аренду')
  await startScene(staff, 'sister')
  await page.getByRole('button', { name: 'Отправить ответ' }).click()
  await expect(number).not.toHaveText(before)
  await page.waitForTimeout(1500)
  await expect(page.getByText('Открыт новый перевод')).toBeVisible()
  await expect(page.locator('textarea')).toHaveValue('')
  await page.locator('textarea').fill('д')
  await expect(page.getByText('Открыт новый перевод')).toBeHidden()
})

test('a request that never ends is reported and the phone recovers', async ({ page }) => {
  test.setTimeout(40_000)
  await page.goto('/receiver')
  await page.locator('textarea').fill('брат прислал за аренду')
  await page.route('**/api/phone/receiver**', () => undefined)
  await page.route('**/api/phone/receiver/answer', () => undefined)
  await page.getByRole('button', { name: 'Отправить ответ' }).click()
  await expect(page.getByRole('button', { name: 'Отправляем…' })).toBeVisible()
  await expect(page.getByText('Нет связи с сервером').first()).toBeVisible({ timeout: 12_000 })
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await expect(page.getByRole('button', { name: 'Отправить ответ' })).toBeVisible({ timeout: 12_000 })
  await expect(page.locator('textarea')).toHaveValue('брат прислал за аренду')
})

test('a double click on Release never skips the question', async ({ page }) => {
  await signIn(page, '/demo')
  await startScene(page, 'stranger')
  await page.goto('/console')
  const file = page.locator('article')
  await expect(file.getByText('Клиенты ещё отвечают')).toBeVisible()
  await page.evaluate(async () => {
    const view = await (await fetch('/api/phone/receiver')).json()
    const body = JSON.stringify({ case_id: view.data.case_id })
    const init = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body }
    await fetch('/api/phone/receiver/deny', init)
    await fetch('/api/phone/receiver/deny', init)
  })
  const release = file.getByRole('button', { name: 'Зачислить' })
  await release.dblclick()
  const confirm = file.getByRole('button', { name: /Подтвердить: зачислить/ })
  await expect(confirm).toBeVisible()
  await expect(file.getByRole('button', { name: 'Отмена' })).toBeFocused()
  await expect(file.getByText('Обращение закрыто')).toBeHidden()
  await page.waitForTimeout(600)
  await file.getByRole('button', { name: 'Отмена' }).click()
  await expect(release).toBeFocused()
  await page.waitForTimeout(600)
  await release.click()
  await page.waitForTimeout(600)
  await confirm.click()
  await expect(file.getByText('Обращение закрыто')).toBeFocused()
})

test('the same screen can be used with the keyboard alone', async ({ browser, page }) => {
  const staff = await (await browser.newContext()).newPage()
  await signIn(staff, '/demo')
  await startScene(staff, 'brother')
  await page.goto('/receiver')
  await page.locator('textarea').focus()
  await page.keyboard.type('друг вернул долг')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'Спасибо, ответ получен' })).toBeFocused()
})

test('the second tap works without moving the focus', async ({ browser, page }) => {
  const staff = await (await browser.newContext()).newPage()
  await signIn(staff, '/demo')
  await startScene(staff, 'stranger')
  await page.goto('/receiver')
  const deny = page.getByRole('button', { name: 'Я не знаю этого человека' })
  await deny.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText('в течение 4 секунд')).toBeVisible()
  await expect(deny).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'Мы можем вернуть эти деньги' })).toBeFocused()
})

test('the hint of the first tap ends on time, also without a connection', async ({ browser, page }) => {
  const staff = await (await browser.newContext()).newPage()
  await signIn(staff, '/demo')
  await startScene(staff, 'stranger')
  await page.goto('/receiver')
  await page.getByRole('button', { name: 'Я не знаю этого человека' }).click()
  const hint = page.getByText('в течение 4 секунд')
  await expect(hint).toBeVisible()
  await page.context().setOffline(true)
  await page.waitForTimeout(4100)
  await expect(hint).toBeHidden({ timeout: 200 })
  await page.context().setOffline(false)
})

test('changing the look of the demo phones keeps what was typed', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await signIn(page, '/demo')
  await startScene(page, 'brother')
  const field = page.frameLocator('iframe[src="/receiver"]').locator('textarea')
  await field.fill('половина ответа')
  await page.getByRole('button', { name: 'Без рамки' }).click()
  await page.waitForTimeout(500)
  await expect(field).toHaveValue('половина ответа')
  // The plain page shows both buttons without scrolling inside the phone.
  const deny = page.frameLocator('iframe[src="/receiver"]').getByRole('button', { name: 'Я не знаю этого человека' })
  expect(await deny.evaluate((button) => button.getBoundingClientRect().bottom <= window.innerHeight)).toBe(true)
  await page.getByRole('button', { name: 'В рамке' }).click()
  await expect(field).toHaveValue('половина ответа')
})

test('a narrow console shows the list or the file', async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 900 })
  await signIn(page, '/console')
  const list = page.getByRole('navigation')
  const file = page.locator('article')
  await expect(list).toBeVisible()
  await expect(file).toBeHidden()
  await expect(list.getByText(/Рискованных фактов: \d из 3/).first()).toBeVisible()
  await list.getByRole('button').first().click()
  await expect(file).toBeVisible()
  await expect(list).toBeHidden()
  await page.getByRole('button', { name: 'К списку' }).click()
  await expect(list).toBeVisible()
  await expect(list.locator('[aria-current="true"]')).toBeFocused()
})

test('one login is enough for all tabs', async ({ context, page }) => {
  await page.goto('/console')
  await expect(page).toHaveURL(/\/login\?next=\/console$/)
  const second = await context.newPage()
  await signIn(second, '/stage')
  await expect(page).toHaveURL(/\/console$/, { timeout: 8000 })
})

test('a failed sign-out does not look like a success', async ({ page }) => {
  await signIn(page, '/console')
  await page.route('**/api/logout', (route) => route.fulfill({ status: 429, json: { success: false, error: 'rate_limited' } }))
  await page.getByRole('button', { name: 'Выйти' }).click()
  await expect(page.getByText('Слишком много запросов')).toBeVisible()
  await expect(page).toHaveURL(/\/console/)
})

test('a wrong address shows a page for people', async ({ page }) => {
  const reply = await page.goto('/no-such-page')
  expect(reply?.status()).toBe(404)
  await expect(page.getByText('Такой страницы нет')).toBeVisible()
  await page.goto('/receiver/')
  await expect(page).toHaveURL(/\/receiver$/)
})

test('the sender on the stage is shown as asked while the phone still asks', async ({ browser, page }) => {
  await signIn(page, '/stage')
  await startScene(page, 'stranger')
  const phone = await (await browser.newContext()).newPage()
  await phone.goto('/receiver')
  const deny = phone.getByRole('button', { name: 'Я не знаю этого человека' })
  await deny.click()
  await expect(phone.getByText('в течение 4 секунд')).toBeVisible()
  await deny.click()
  const sender = page.getByRole('region', { name: 'Телефон отправителя' })
  await expect(sender.getByText('Ждём ответ')).toBeVisible()
  await expect(sender.getByText('У специалиста')).toBeHidden()
  await expect(page.getByRole('region', { name: 'Телефон получателя' }).getByText('Мы можем вернуть эти деньги')).toBeVisible()
})

test('a lost reply leaves no error on the next screen', async ({ browser, page }) => {
  const staff = await (await browser.newContext()).newPage()
  await signIn(staff, '/demo')
  await startScene(staff, 'stranger')
  await page.goto('/receiver')
  const deny = page.getByRole('button', { name: 'Я не знаю этого человека' })
  await deny.click()
  await expect(page.getByText('в течение 4 секунд')).toBeVisible()
  // The server takes the second tap, but its reply never arrives.
  await page.route('**/api/phone/receiver/deny', async (route) => {
    await route.fetch()
    await route.abort()
  })
  await deny.click()
  await expect(page.getByRole('heading', { name: 'Мы можем вернуть эти деньги' })).toBeVisible()
  await expect(page.getByText('Нет связи с сервером')).toBeHidden()
})

test('a release that fails after another case was opened is reported', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await signIn(page, '/console')
  const list = page.getByRole('navigation').getByRole('listitem').getByRole('button')
  await list.filter({ hasText: 'Бахыт' }).click()
  const file = page.locator('article')
  await file.getByRole('button', { name: 'Зачислить' }).click()
  await page.waitForTimeout(600)
  await page.route('**/api/cases/*/release', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 600))
    await route.fulfill({ status: 429, json: { success: false, error: 'rate_limited' } })
  })
  await file.getByRole('button', { name: /Подтвердить: зачислить/ }).click()
  await list.filter({ hasText: 'Жанар' }).click()
  await expect(page.getByText('Слишком много запросов')).toBeVisible()
})

test('a new screen starts at its top', async ({ browser, page }) => {
  const staff = await (await browser.newContext()).newPage()
  await signIn(staff, '/demo')
  await startScene(staff, 'stranger')
  await page.setViewportSize({ width: 360, height: 560 })
  await page.goto('/receiver')
  const deny = page.getByRole('button', { name: 'Я не знаю этого человека' })
  await deny.scrollIntoViewIfNeeded()
  await deny.click()
  // The hint stands above the button, so it is on the screen wherever the button is.
  await expect(page.getByText('в течение 4 секунд')).toBeInViewport({ ratio: 0.99 })
  await deny.click()
  const heading = page.getByRole('heading', { name: 'Мы можем вернуть эти деньги' })
  await expect(heading).toBeFocused()
  await expect(heading).toBeInViewport({ ratio: 0.99 })
})

test('all texts of every phone screen have at least 18 px', async ({ page }) => {
  for (const status of ['question', 'waiting', 'credited', 'with_specialist', 'held', 'returned', 'return_offer']) {
    const view = { ...HELD, status, denied: true, message: 'за квартиру', answer_by: '2026-11-26T12:00:00+05:00' }
    await showPhone(page, view)
    await page.goto('/receiver')
    await expect(page.locator('main h1')).toBeVisible()
    const small = await page.locator('main, footer').evaluateAll((areas) =>
      areas
        .flatMap((area) => [...area.querySelectorAll('*')])
        .filter((one) => !one.closest('.sr-only') && [...one.childNodes].some((node) => node.nodeType === 3 && node.textContent?.trim()))
        .filter((one) => Number.parseFloat(getComputedStyle(one).fontSize) < 18)
        .map((one) => one.textContent),
    )
    expect(small, status).toEqual([])
    await page.unroute('**/api/phone/receiver')
  }
})

test('the stage fits common screens in three languages', async ({ browser, page }) => {
  test.setTimeout(60_000)
  await signIn(page, '/stage')
  await startScene(page, 'sister')
  const phones = await (await browser.newContext()).newPage()
  for (const [side, text] of [['receiver', 'друг вернул долг'], ['sender', 'сестре на лечение']] as const) {
    await phones.goto(`/${side}`)
    await phones.locator('textarea').fill(text)
    await phones.getByRole('button', { name: 'Отправить ответ' }).click()
  }
  await expect(page.getByText('Истории расходятся')).toBeVisible()
  for (const [width, height] of [[1366, 768], [1440, 900], [1536, 730], [1536, 864], [1600, 900], [1920, 937], [1920, 1080]] as const) {
    await page.setViewportSize({ width, height })
    for (const name of [/Русский/, /Қазақша/, /English/]) {
      await page.getByRole('button', { name }).click()
      await page.waitForTimeout(300)
      const over = await page.evaluate(() => document.documentElement.scrollHeight - document.documentElement.clientHeight)
      expect(over, `${width}x${height} ${name}`).toBeLessThanOrEqual(0)
      const cut = await page.locator('section').evaluateAll((all) => all.filter((one) => one.scrollWidth > one.clientWidth + 1).length)
      expect(cut, `${width}x${height} ${name}`).toBe(0)
    }
  }
})
