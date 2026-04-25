#!/usr/bin/env node
// Builds the webapp for production and stages docs/app/ ready to commit.
// Cross-platform replacement for build-prod.sh.
// Usage: npm run build:prod   (from the webapp/ directory)

import { spawnSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WEBAPP_DIR = resolve(__dirname, '..');
const REPO_ROOT = resolve(WEBAPP_DIR, '..');
const ENV_FILE = resolve(WEBAPP_DIR, '.env.local');
const PROD_URL = 'https://api.cischi.dev';
const DEV_URL = 'http://localhost:8000';

function writeEnv(url) {
  writeFileSync(ENV_FILE, `VITE_API_BASE_URL=${url}\n`);
}

function run(cmd, args, cwd) {
  const result = spawnSync(cmd, args, {
    cwd,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
  if (result.status !== 0) {
    const code = result.status ?? 1;
    throw new Error(`${cmd} ${args.join(' ')} exited with ${code}`);
  }
}

let exitCode = 0;
try {
  console.log(`-> Switching .env.local to production URL (${PROD_URL})...`);
  writeEnv(PROD_URL);

  console.log('-> Building webapp...');
  run('npm', ['run', 'build'], WEBAPP_DIR);

  console.log('-> Staging docs/app/ ...');
  run('git', ['add', 'docs/app/'], REPO_ROOT);

  console.log('');
  console.log('Build complete and docs/app/ staged.');
  console.log("Run:  git commit -m 'chore: update webapp build'");
} catch (err) {
  console.error(err.message);
  exitCode = 1;
} finally {
  writeEnv(DEV_URL);
  console.log(`<- Restored .env.local -> ${DEV_URL}`);
}

process.exit(exitCode);
