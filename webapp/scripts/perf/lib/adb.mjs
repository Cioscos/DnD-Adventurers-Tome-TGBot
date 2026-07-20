import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

const run = promisify(execFile)

/** Socket abstract delle WebView in debug sul device (richiede adb connesso). */
export async function findWebViewSockets() {
  const { stdout } = await run('adb', ['shell', 'cat /proc/net/unix'])
  const names = stdout
    .split('\n')
    .map((l) => l.match(/@(webview_devtools_remote_\d+)/)?.[1])
    .filter(Boolean)
  return [...new Set(names)]
}

export async function forwardDevtools({ port = 9222, socket } = {}) {
  let target = socket
  if (!target) {
    const sockets = await findWebViewSockets()
    if (sockets.length === 0) {
      throw new Error(
        'Nessuna WebView in debug trovata. Verifica: (1) adb connesso (`adb devices`), ' +
          '(2) "Enable WebView Debug" attivo nel menu debug di Telegram, (3) Mini App aperta.',
      )
    }
    target = sockets[sockets.length - 1]
  }
  await run('adb', ['forward', `tcp:${port}`, `localabstract:${target}`])
  return { port, socket: target }
}
