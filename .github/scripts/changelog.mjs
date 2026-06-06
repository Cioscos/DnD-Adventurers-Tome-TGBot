#!/usr/bin/env node
// Single source of truth for the changelog/version automation.
//
//   node .github/scripts/changelog.mjs check <latestTag> <label>
//        Verifies (used by the PR guard): the top changelog entry's version equals
//        bump(latestTag, label), all three manifests agree, and the entry has content.
//        Exits non-zero with a human-readable message on any violation.
//
//   node .github/scripts/changelog.mjs version   → prints the current version (top entry)
//   node .github/scripts/changelog.mjs notes      → prints the GitHub Release body (markdown)
//
// The webapp consumes the same changelog.json directly; this script never writes the repo.

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const CHANGELOG = resolve(ROOT, 'webapp/src/data/changelog.json')
const PKG = resolve(ROOT, 'webapp/package.json')
const PYPROJECT = resolve(ROOT, 'pyproject.toml')

const CATEGORIES = [
  { key: 'added', emoji: '✨', it: 'Nuove funzionalità', en: 'New features' },
  { key: 'improved', emoji: '🛠', it: 'Migliorie', en: 'Improvements' },
  { key: 'fixed', emoji: '🐛', it: 'Correzioni', en: 'Fixes' },
]

function fail(msg) {
  console.error(`::error::${msg}`)
  process.exit(1)
}

function topEntry() {
  const data = JSON.parse(readFileSync(CHANGELOG, 'utf8'))
  if (!Array.isArray(data.entries) || data.entries.length === 0) {
    fail('changelog.json non contiene voci.')
  }
  return data.entries[0]
}

function pkgVersion() {
  return JSON.parse(readFileSync(PKG, 'utf8')).version
}

function pyVersion() {
  const m = readFileSync(PYPROJECT, 'utf8').match(/^\s*version\s*=\s*"([^"]+)"/m)
  return m ? m[1] : null
}

function parseSemver(v) {
  const m = String(v).replace(/^v/, '').match(/^(\d+)\.(\d+)\.(\d+)$/)
  if (!m) return null
  return { major: +m[1], minor: +m[2], patch: +m[3] }
}

function bump(latestTag, label) {
  const base = parseSemver(latestTag) ?? { major: 0, minor: 0, patch: 0 }
  switch (label) {
    case 'major': return `${base.major + 1}.0.0`
    case 'minor': return `${base.major}.${base.minor + 1}.0`
    case 'patch': return `${base.major}.${base.minor}.${base.patch + 1}`
    default: return null
  }
}

function entryHasContent(entry) {
  return CATEGORIES.some(({ key }) => {
    const c = entry[key]
    return c && ((c.it && c.it.length) || (c.en && c.en.length))
  })
}

function renderNotes(entry) {
  const lines = []
  if (entry.title) lines.push(`> ${entry.title.it}${entry.title.en ? ` · ${entry.title.en}` : ''}`, '')

  const renderLang = (lang, heading) => {
    const blocks = []
    for (const { key, emoji, it, en } of CATEGORIES) {
      const c = entry[key]
      const items = c?.[lang]
      if (!items || items.length === 0) continue
      blocks.push(`### ${emoji} ${lang === 'it' ? it : en}`)
      blocks.push(...items.map((l) => `- ${l}`))
      blocks.push('')
    }
    if (blocks.length === 0) return
    lines.push(`## ${heading}`, '', ...blocks)
  }

  renderLang('it', '🇮🇹 Italiano')
  renderLang('en', '🇬🇧 English')
  return lines.join('\n').trim() + '\n'
}

const [cmd, ...args] = process.argv.slice(2)

switch (cmd) {
  case 'version':
    process.stdout.write(topEntry().version)
    break

  case 'notes':
    process.stdout.write(renderNotes(topEntry()))
    break

  case 'check': {
    const [latestTag, label] = args
    if (!['major', 'minor', 'patch'].includes(label)) {
      fail(`Label di release non valida: "${label}". Attesa una fra major|minor|patch.`)
    }
    const top = topEntry()
    const py = pyVersion()
    const pkg = pkgVersion()

    // Bootstrap: nessuna release ancora (nessun tag v*, oppure v0.0.0). La versione seed
    // viene accettata così com'è (non è derivabile da una label). Dalla release successiva
    // vale la regola stretta `ultimo_tag + label`.
    const prior = parseSemver(latestTag)
    const isBootstrap = !prior || (prior.major === 0 && prior.minor === 0 && prior.patch === 0)

    if (isBootstrap) {
      if (!parseSemver(top.version) || top.version === '0.0.0') {
        fail(`Versione seed non valida in changelog.json: "${top.version}".`)
      }
    } else {
      const expected = bump(latestTag, label)
      if (top.version !== expected) {
        fail(`La versione in cima a changelog.json è "${top.version}" ma con label "${label}" sull'ultimo tag "${latestTag}" è attesa "${expected}". Aggiorna la voce o la label.`)
      }
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(top.date || '')) {
      fail(`La voce ${top.version} ha una data non valida ("${top.date}"). Usa il formato YYYY-MM-DD.`)
    }
    if (!entryHasContent(top)) {
      fail(`La voce ${top.version} non ha contenuti (added/improved/fixed tutti vuoti).`)
    }
    if (pkg !== top.version) {
      fail(`webapp/package.json versione "${pkg}" non combacia con changelog "${top.version}".`)
    }
    if (py !== top.version) {
      fail(`pyproject.toml versione "${py}" non combacia con changelog "${top.version}".`)
    }
    console.log(`OK: versione ${top.version} coerente (changelog, package.json, pyproject.toml) e attesa dalla label "${label}".`)
    break
  }

  default:
    fail(`Comando sconosciuto: "${cmd}". Usa: check | version | notes.`)
}
