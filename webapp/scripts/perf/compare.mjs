#!/usr/bin/env node
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { renderComparison } from './lib/report.mjs'

const [baseDir, curDir] = process.argv.slice(2)
if (!baseDir || !curDir) {
  console.error('Uso: node scripts/perf/compare.mjs <dirBaseline> <dirCorrente>')
  process.exit(1)
}

const baseline = JSON.parse(await readFile(path.join(baseDir, 'run.json'), 'utf8'))
const current = JSON.parse(await readFile(path.join(curDir, 'run.json'), 'utf8'))
const md = renderComparison(baseline, current)
await writeFile(path.join(curDir, 'comparison.md'), md)
console.log(md)
