const CATEGORIES = [
  '-*',
  'devtools.timeline',
  'disabled-by-default-devtools.timeline',
  'disabled-by-default-devtools.timeline.frame',
  'blink.user_timing',
]

export async function startTracing(page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Tracing.start', {
    traceConfig: { includedCategories: CATEGORIES },
    transferMode: 'ReturnAsStream',
  })
  return cdp
}

export async function stopTracing(cdp) {
  const complete = new Promise((resolve) => cdp.once('Tracing.tracingComplete', resolve))
  await cdp.send('Tracing.end')
  const { stream } = await complete
  let data = ''
  for (;;) {
    const { data: chunk, base64Encoded, eof } = await cdp.send('IO.read', { handle: stream })
    data += base64Encoded ? Buffer.from(chunk, 'base64').toString('utf8') : chunk
    if (eof) break
  }
  await cdp.send('IO.close', { handle: stream })
  await cdp.detach()
  const parsed = JSON.parse(data)
  return Array.isArray(parsed) ? parsed : parsed.traceEvents
}
