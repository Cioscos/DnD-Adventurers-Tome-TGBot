import { chromium } from '@playwright/test'

const APP_URL_PATTERNS = [/cioscos\.github\.io/, /localhost/, /127\.0\.0\.1/]

/** Si collega alla WebView già inoltrata su localhost:<port> (vedi adb.mjs). */
export async function connectDevice({ port = 9222 } = {}) {
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`)
  const pages = browser.contexts().flatMap((c) => c.pages())
  const page =
    pages.find((p) => APP_URL_PATTERNS.some((rx) => rx.test(p.url()))) ?? pages[0]
  if (!page) throw new Error('Nessuna pagina trovata nella WebView.')
  return { browser, page, close: () => browser.close() }
}

/** Chrome locale headed, viewport mobile, CPU throttling per simulare il device. */
export async function launchLocal({ url, cpuThrottle = 6 } = {}) {
  const browser = await chromium.launch({ headless: false })
  const context = await browser.newContext({
    viewport: { width: 375, height: 667 },
    isMobile: true,
    hasTouch: true,
    deviceScaleFactor: 2,
  })
  const page = await context.newPage()
  const cdp = await context.newCDPSession(page)
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: cpuThrottle })
  if (url) await page.goto(url)
  return { browser, page, close: () => browser.close() }
}
