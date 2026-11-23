// API usa e getta per i controlli Playwright: database e file caricati in una cartella temporanea.
import { spawn } from 'node:child_process'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..')
const cwd = mkdtempSync(path.join(tmpdir(), 'caccia-api-'))
const python = ['.venv/Scripts/python.exe', '.venv/bin/python'].map((p) => path.join(repo, p)).find(existsSync)
if (!python) throw new Error('.venv non trovato: lancia prima `uv sync` da Windows')

const api = spawn(python, ['-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8020', '--app-dir', repo], {
  cwd,
  stdio: 'inherit',
  // Le variabili vincono sul .env del repo: nessun token vero, nessun messaggio agli utenti.
  env: { ...process.env, DB_PATH: path.join(cwd, 'caccia.db'), DEV_USER_ID: '9001', BOT_TOKEN: '123:finto', DEV_CHAT_ID: '',
         SEND_CAMPAIGN_MESSAGES: '0', ANNOUNCE_RELEASES: '0' },
})
api.on('exit', (codice) => process.exit(codice ?? 1))
for (const s of ['SIGINT', 'SIGTERM']) process.on(s, () => api.kill())
